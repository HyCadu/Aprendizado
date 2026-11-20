"""Checagem de dependências e GPU. Só lê: não instala nem altera nada (o setup continua sendo das skills)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .core import AI_STREAM_CLIPPER, CLIPPER_CONFIG, REPO, SKILLS, is_authentication_error
from .storage import read_json

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
SCRIPTS = SKILLS / "cortes-youtube" / "scripts"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    required: bool = True


def run(cmd: list[str], timeout: float = 20) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def find_claude(custom: str = "") -> str | None:
    if custom and Path(custom).is_file():
        return custom
    p = shutil.which("claude")
    if p:
        return p
    for cand in (Path.home() / ".local" / "bin" / "claude.exe",
                 Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"):
        if cand.is_file():
            return str(cand)
    return None


def parse_claude_auth_status(returncode: int, output: str) -> tuple[str, str]:
    text = (output or "").strip()
    lowered = text.lower()

    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        logged_in = payload.get("loggedIn", payload.get("isLoggedIn", payload.get("authenticated")))
        if isinstance(logged_in, bool):
            if logged_in:
                return "connected", "Claude Code está autenticado."
            return "disconnected", "Claude Code está desconectado. Faça login para gerar clipes."
        if isinstance(logged_in, str) and logged_in.lower() in ("true", "false"):
            if logged_in.lower() == "true":
                return "connected", "Claude Code está autenticado."
            return "disconnected", "Claude Code está desconectado. Faça login para gerar clipes."

    logged_out_markers = ("not logged in", "logged out", "please run /login", "not authenticated",
                          "not signed in", "login required", "no active session")
    if any(marker in lowered for marker in logged_out_markers):
        return "disconnected", "Claude Code está desconectado. Faça login para gerar clipes."
    if is_authentication_error(text):
        return "auth_error", "Claude Code retornou um erro de autenticação. Tente autenticar novamente."

    if returncode == 0 and any(marker in lowered for marker in ("logged in", "authenticated", "signed in")):
        return "connected", "Claude Code está autenticado."
    if returncode == 0:
        return "auth_error", "Não foi possível confirmar a autenticação do Claude Code. Verifique novamente."
    return "auth_error", "Não foi possível verificar a autenticação do Claude Code. Verifique novamente."


def check_claude_auth(custom: str = "") -> tuple[str, str]:
    claude = find_claude(custom)
    if not claude:
        return "unavailable", "Claude Code não foi encontrado. Configure ou instale o Claude Code."

    returncode, output = run([claude, "auth", "status"], timeout=20)
    if returncode == -1 and any(marker in output.lower() for marker in ("winerror 2", "no such file", "not found")):
        return "unavailable", "Claude Code não pôde ser iniciado. Confira o caminho nas configurações."
    return parse_claude_auth_status(returncode, output)


def launch_claude_login(custom: str = "") -> tuple[bool, str]:
    claude = find_claude(custom)
    if not claude:
        return False, "Claude Code não foi encontrado. Configure ou instale o Claude Code."
    if os.name != "nt":
        return False, "A abertura de um terminal interativo está disponível no Windows."

    command = subprocess.list2cmdline([claude, "auth", "login"])
    terminal = os.environ.get("COMSPEC", "cmd.exe")
    try:
        subprocess.Popen([terminal, "/k", command], cwd=str(REPO),
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    except (OSError, ValueError):
        return False, "Não foi possível abrir o terminal para autenticar o Claude Code."
    return True, "Terminal do Claude Code aberto. Conclua o login e verifique novamente."


def find_python() -> str | None:
    """O Python que as skills usam (`python` no PATH). O alias da Microsoft Store não serve."""
    p = shutil.which("python")
    if p and "WindowsApps" not in p:
        return p
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    for d in sorted(local.glob("Python3*"), reverse=True):
        if (d / "python.exe").is_file():
            return str(d / "python.exe")
    return p


def gpu_info() -> dict:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"ok": False, "detail": "nvidia-smi não encontrado (sem placa NVIDIA ou driver)."}
    fields = "name,memory.total,memory.used,driver_version,temperature.gpu,utilization.gpu"
    code, out = run([smi, f"--query-gpu={fields}", "--format=csv,noheader,nounits"], 10)
    if code != 0 or not out.strip():
        return {"ok": False, "detail": out.strip()[:200] or "nvidia-smi falhou"}
    parts = [p.strip() for p in out.strip().splitlines()[0].split(",")]
    keys = ["name", "mem_total", "mem_used", "driver", "temp", "util"]
    info = dict(zip(keys, parts))
    code, cuda = run([smi], 10)
    for line in cuda.splitlines():
        m = re.search(r"CUDA (?:UMD )?Version:\s*([\d.]+)", line)
        if m:
            info["cuda"] = m.group(1)
            break
    info["ok"] = True
    return info


def clipper_config() -> dict:
    return read_json(CLIPPER_CONFIG, {}) or {}


def check_all(claude_custom: str = "") -> list[Check]:
    checks: list[Check] = []
    py = find_python()
    if py:
        code, out = run([py, "--version"])
        checks.append(Check("Python", code == 0, f"{out.strip()}  ·  {py}"))
        on_path = shutil.which("python")
        if not on_path or "WindowsApps" in on_path:
            checks.append(Check("'python' no PATH", False,
                                "Aponta para a Microsoft Store. O app corrige isso sozinho nos cortes; "
                                "para o terminal, reinstale o Python marcando 'Add python.exe to PATH'.",
                                required=False))
    else:
        checks.append(Check("Python", False, "Instale em python.org marcando 'Add python.exe to PATH'."))

    cl = find_claude(claude_custom)
    if cl:
        code, out = run([cl, "--version"])
        checks.append(Check("Claude Code", code == 0, f"{out.strip()}  ·  {cl}"))
    else:
        checks.append(Check("Claude Code", False, "Não encontrado. Rode: irm https://claude.ai/install.ps1 | iex"))

    git = shutil.which("git")
    checks.append(Check("Git", bool(git), git or "Instale em git-scm.com", required=False))

    for skill in ("cortes-youtube", "clipar-gta-br"):
        f = SKILLS / skill / "SKILL.md"
        checks.append(Check(f"Skill {skill}", f.is_file(), str(f.parent)))
    asc = AI_STREAM_CLIPPER / "SKILL.md"
    try:
        patched = "Portuguese" in asc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        patched = False
    checks.append(Check("Skill ai-stream-clipper (pt-BR)", patched,
                        str(AI_STREAM_CLIPPER) if patched else
                        "Rode: powershell -ExecutionPolicy Bypass -File clipper-gta-br\\instalar.ps1"))

    cfg = clipper_config()
    checks.append(Check("Setup do clipper", bool(cfg),
                        f"{cfg.get('device', '?').upper()} · {cfg.get('model', '?')} · {cfg.get('encoder', '?')}"
                        if cfg else "No Claude, digite: configura o clipper"))

    if py:
        mods = ["yt_dlp", "faster_whisper", "cv2", "numpy", "fontTools"]
        code_s = ("import importlib.util as u,sys\n"
                  f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
                  f"for m in {mods!r}: print(m, bool(u.find_spec(m)))\n"
                  "import cl_common as c\n"
                  "for b in ('ffmpeg','ffprobe','deno','node'): print('BIN', b, c.which(b) or '')\n")
        code, out = run([py, "-I", "-c", code_s], 40)
        found = {}
        bins = {}
        for line in out.splitlines():
            p = line.split(" ", 2)
            if p[0] == "BIN" and len(p) >= 2:
                bins[p[1]] = p[2] if len(p) > 2 else ""
            elif len(p) == 2:
                found[p[0]] = p[1] == "True"
        labels = {"yt_dlp": "yt-dlp", "faster_whisper": "faster-whisper", "cv2": "OpenCV",
                  "numpy": "NumPy", "fontTools": "fontTools"}
        for m in mods:
            checks.append(Check(f"Pacote {labels[m]}", found.get(m, False),
                                "" if found.get(m) else f"Falta. No Claude: configura o clipper"))
        ff = bins.get("ffmpeg", "")
        if ff:
            code, out = run([ff, "-hide_banner", "-version"])
            ver = out.splitlines()[0][:70] if out else ""
            code2, filt = run([ff, "-hide_banner", "-filters"])
            checks.append(Check("FFmpeg", True, f"{ver}  ·  {ff}"))
            checks.append(Check("FFmpeg com libass (legendas)", " ass " in filt or "subtitles" in filt))
        else:
            checks.append(Check("FFmpeg", False, "Não encontrado. No Claude: configura o clipper"))
        js = bins.get("deno") or bins.get("node")
        checks.append(Check("Runtime JS (deno/node) p/ YouTube", bool(js), js or "Instale o deno: deno.com"))
    return checks


def system_summary() -> dict:
    return {"os": f"Windows {sys.getwindowsversion().build}" if os.name == "nt" else os.name}
