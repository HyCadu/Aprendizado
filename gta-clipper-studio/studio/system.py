"""Checagem de dependências e GPU. Só lê: não instala nem altera nada (o setup continua sendo das skills)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .core import AI_STREAM_CLIPPER, CLIPPER_CONFIG, SKILLS
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


# Placa AMD / Intel Arc (Windows): nome e driver pelo WMI, memória total pelo registro (o AdapterRAM do WMI
# trava em 4 GB), uso e memória ocupada pelos contadores de desempenho da GPU. Temperatura o Windows não dá.
_PS_GPU = r"""
$v = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'Radeon|AMD|Arc' } | Select-Object -First 1
if (-not $v) { exit 3 }
$cls = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
$mem = 0
Get-ChildItem $cls -ErrorAction SilentlyContinue | ForEach-Object {
  $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
  if ($p -and $p.DriverDesc -eq $v.Name -and $p.'HardwareInformation.qwMemorySize') { $mem = $p.'HardwareInformation.qwMemorySize' }
}
$s = (Get-Counter '\GPU Engine(*engtype_3D)\Utilization Percentage','\GPU Adapter Memory(*)\Dedicated Usage' -ErrorAction SilentlyContinue).CounterSamples
$util = ($s | Where-Object Path -match 'gpu engine' | Measure-Object CookedValue -Sum).Sum
$used = ($s | Where-Object Path -match 'adapter memory' | Measure-Object CookedValue -Maximum).Maximum
"$($v.Name)|$($v.DriverVersion)|$mem|$util|$used"
"""


def _gpu_info_windows() -> dict | None:
    if os.name != "nt":
        return None
    code, out = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS_GPU], 20)
    line = next((ln for ln in out.splitlines() if ln.count("|") == 4), "")
    if code != 0 or not line:
        return None
    name, driver, mem, util, used = (x.strip() for x in line.split("|"))

    def num(x):
        try:
            return float(x)
        except ValueError:
            return None

    info = {"ok": True, "vendor": "AMD" if re.search(r"radeon|amd", name, re.I) else "Intel",
            "name": name, "driver": driver, "temp": ""}
    if num(mem):
        info["mem_total"] = f"{num(mem) / 2**20:.0f}"
    if num(used) is not None:
        info["mem_used"] = f"{num(used) / 2**20:.0f}"
    if num(util) is not None:
        info["util"] = f"{min(100.0, num(util)):.0f}"
    # transcrição na placa: whisper.cpp + Vulkan (setup --vulkan), ver cl_whispercpp nas skills
    info["api"] = "Vulkan (whisper.cpp)" if clipper_config().get("device") == "vulkan" else \
        "Vulkan: não configurado (setup --vulkan)"
    return info


def gpu_info() -> dict:
    smi = shutil.which("nvidia-smi")
    if not smi:
        other = _gpu_info_windows()
        if other:
            return other
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
    info["vendor"] = "NVIDIA"
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
