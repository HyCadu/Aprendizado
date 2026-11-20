"""Configurações do app, histórico de processamentos e leitura (somente leitura) das pastas de cortes."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .core import DEFAULT_TW_OUT, DEFAULT_YT_OUT, TWITCH, YOUTUBE

DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "GTAClipperStudio"
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "history.json"
LOG_DIR = DATA_DIR / "logs"


def read_json(p: Path, default):
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


# ---------------------------------------------------------------- configurações
class Settings:
    DEFAULTS = {
        "youtube_out": str(DEFAULT_YT_OUT),
        "twitch_out": str(DEFAULT_TW_OUT),
        "claude_path": "",
        "last_platform": YOUTUBE,
        "last_clips": 3,
        "last_lang": "auto",
        "keep_original_captions": False,
        "zoom_on_narration": True,
        "make_cover": True,
    }

    def __init__(self, path: Path = SETTINGS_FILE):
        self.path = path
        self.data = dict(self.DEFAULTS)
        self.data.update({k: v for k, v in read_json(path, {}).items() if k in self.DEFAULTS})

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v

    def save(self):
        write_json(self.path, self.data)

    def out_dir(self, platform: str) -> Path:
        return Path(self.data["youtube_out" if platform == YOUTUBE else "twitch_out"]).expanduser()

    def library_roots(self) -> list[tuple[str, Path]]:
        roots = [(YOUTUBE, self.out_dir(YOUTUBE)), (TWITCH, self.out_dir(TWITCH))]
        # As pastas padrão das skills continuam visíveis mesmo se o usuário escolheu outras.
        for plat, d in ((YOUTUBE, DEFAULT_YT_OUT), (TWITCH, DEFAULT_TW_OUT)):
            if all(d.resolve() != r.resolve() for _, r in roots):
                roots.append((plat, d))
        return roots


# ---------------------------------------------------------------- histórico
class History:
    def __init__(self, path: Path = HISTORY_FILE):
        self.path = path
        self.items: list[dict] = read_json(path, [])
        if not isinstance(self.items, list):
            self.items = []

    def add(self, item: dict):
        self.items.insert(0, item)
        del self.items[200:]
        write_json(self.path, self.items)

    def update_last(self, **kw):
        if self.items:
            self.items[0].update(kw)
            write_json(self.path, self.items)

    def merged(self, settings: Settings) -> list[dict]:
        """Histórico do app + registros das skills (processados.json / processadas.json)."""
        out = list(self.items)
        known = {i.get("url") for i in out}
        for plat, name in ((YOUTUBE, "processados.json"), (TWITCH, "processadas.json")):
            for root in {settings.out_dir(plat), DEFAULT_YT_OUT if plat == YOUTUBE else DEFAULT_TW_OUT}:
                for url, rec in (read_json(root / name, {}) or {}).items():
                    if url in known or not isinstance(rec, dict):
                        continue
                    known.add(url)
                    out.append({"url": url, "platform": plat, "status": rec.get("status", "?"),
                                "when": rec.get("quando", ""), "note": rec.get("nota", ""),
                                "source": "skill"})
        out.sort(key=lambda i: i.get("when", ""), reverse=True)
        return out


# ---------------------------------------------------------------- biblioteca
SHEET_CELL = (0, 0, 270, 480)  # cl_render.contact_sheet: tile=6x2 de 270x480


@dataclass
class Clip:
    path: Path
    platform: str
    job_dir: Path
    title: str = ""
    hook: str = ""
    channel: str = ""
    video_title: str = ""
    source: str = ""
    score: float | None = None
    duration: float | None = None
    sync: str = ""
    mtime: float = 0.0
    size: int = 0
    extras: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def sheet(self) -> Path:
        return self.path.parent / "sheet.jpg"

    @property
    def cover(self) -> Path:
        """Capa gerada pelo render: <clipe>_capa.jpg ao lado do .mp4."""
        return self.path.with_name(self.path.stem + "_capa.jpg")

    @property
    def thumb(self) -> Path:
        return self.cover if self.cover.is_file() else self.sheet

    @property
    def post_md(self) -> Path:
        return self.path.parent / "post.md"

    @property
    def sync_state(self) -> str:
        s = self.sync.lower()
        if "fail" in s:
            return "fail"
        if s.startswith("sync ok") or "sync ok" in s:
            return "ok"
        if s:
            return "check"
        return ""


def _sync_lines(report: Path) -> dict[str, str]:
    """report.md: linha do caminho do .mp4 seguida da linha 'sync ...'."""
    out = {}
    try:
        lines = report.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return out
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.lower().endswith(".mp4") and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt.lower().startswith("sync"):
                out[Path(s).name.lower()] = nxt
    return out


def scan_library(roots: list[tuple[str, Path]]) -> list[Clip]:
    clips: list[Clip] = []
    seen = set()
    for plat, root in roots:
        if not root.is_dir():
            continue
        for job in root.iterdir():
            cdir = job / "clips"
            if not cdir.is_dir():
                continue
            jobj = read_json(job / "job.json", {}) or {}
            syncs = _sync_lines(job / "report.md")
            for mp4 in sorted(cdir.glob("*/*.mp4")):
                key = str(mp4.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                try:
                    st = mp4.stat()
                except OSError:
                    continue
                pick = (read_json(mp4.parent / "clip.json", {}) or {}).get("pick", {}) or {}
                clips.append(Clip(
                    path=mp4, platform=plat, job_dir=job,
                    title=pick.get("title") or mp4.stem, hook=pick.get("hook", ""),
                    channel=jobj.get("channel", ""), video_title=jobj.get("title", job.name),
                    source=jobj.get("source") or jobj.get("url", ""),
                    score=pick.get("score"), duration=pick.get("duration"),
                    sync=syncs.get(mp4.name.lower(), ""), mtime=st.st_mtime, size=st.st_size))
    clips.sort(key=lambda c: c.mtime, reverse=True)
    return clips


def library_stats(clips: list[Clip]) -> dict:
    now = time.time()
    return {
        "clips": len(clips),
        "jobs": len({c.job_dir for c in clips}),
        "week": sum(1 for c in clips if now - c.mtime < 7 * 86400),
        "seconds": sum(c.duration or 0 for c in clips),
        "youtube": sum(1 for c in clips if c.platform == YOUTUBE),
        "twitch": sum(1 for c in clips if c.platform == TWITCH),
        "sync_ok": sum(1 for c in clips if c.sync_state == "ok"),
    }


def fmt_duration(sec: float | None) -> str:
    if not sec:
        return "--"
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}:{s:02d}"


def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def safe_log_name(prefix: str) -> str:
    return re.sub(r"[^\w\-]", "_", prefix) + time.strftime("_%Y-%m-%d_%H%M%S") + ".log"
