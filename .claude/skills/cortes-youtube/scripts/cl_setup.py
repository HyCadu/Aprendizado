"""Checks and installs everything the clipper needs. Prints a ready / not-ready report."""
from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from cl_common import (CONFIG_DIR, FONTS, IS_MAC, IS_WIN, YUNET, add_cuda_dll_dirs, load_config, log, run,
                       save_config, which)

PIP = {  # import name -> pip package
    "yt_dlp": "yt-dlp[default]",
    "faster_whisper": "faster-whisper",
    "cv2": "opencv-python",
    "numpy": "numpy",
    "fontTools": "fonttools",
}
OPTIONAL = ()


def pip_install(pkgs):
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check"] + pkgs
    log("  pip install " + " ".join(pkgs))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        log("  pip failed:\n" + r.stderr[-1500:])
    return r.returncode == 0


def has_module(name):
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def is_store_python() -> bool:
    """Python da Microsoft Store: o pip instala os pacotes na pasta do usuário, que o `python -I` ignora.
    Nada que o pip faça resolve; precisa do Python do python.org."""
    return IS_WIN and any("WindowsApps" in (p or "") for p in (sys.executable, sys.prefix, sys.base_prefix))


def install_python_org():
    if which("winget"):
        log("  instalando o Python do python.org com winget (só para o seu usuário)...")
        subprocess.run(["winget", "install", "-e", "--id", "Python.Python.3.13", "--scope", "user",
                        "--accept-source-agreements", "--accept-package-agreements", "--silent", "--override",
                        "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0"])


def audio_decode_ok():
    """faster-whisper lê o áudio com o PyAV. O PyAV 17+ removeu `metadata_errors`, que o faster-whisper 1.2
    ainda usa: a transcrição quebra até na CPU. Testa num processo novo (pega a versão recém-instalada)."""
    wav = Path(tempfile.gettempdir()) / "stream_clipper_decode.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    code = "import sys;from faster_whisper.audio import decode_audio;print('DECODE_OK', len(decode_audio(sys.argv[1])))"
    r = subprocess.run([sys.executable, "-I", "-c", code, str(wav)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return "DECODE_OK" in r.stdout, (r.stderr or "").strip().splitlines()[-1:] or [""]


# ---------------------------------------------------------------- modelo do whisper
MODEL_FILES = ("config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.json",
               "vocabulary.txt")
STALL_SECS = 120   # download parado por mais que isso = travado


def model_dir(name: str) -> Path:
    return CONFIG_DIR / "models" / name


def _dir_size(p: Path) -> int:
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0


def _repo_files(repo: str) -> dict:
    """{arquivo: tamanho} do modelo no Hugging Face (só os que o faster-whisper usa)."""
    url = f"https://huggingface.co/api/models/{repo}?blobs=true"
    curl = which("curl")
    if curl:
        txt = subprocess.run([curl, "-sS", "-L", "--fail", "--max-time", "60", url], capture_output=True,
                             text=True, encoding="utf-8").stdout
    else:
        from urllib.request import urlopen
        with urlopen(url, timeout=60) as f:
            txt = f.read().decode("utf-8")
    info = json.loads(txt)
    return {s["rfilename"]: (s.get("lfs") or {}).get("size") or s.get("size")
            for s in info.get("siblings", []) if s["rfilename"] in MODEL_FILES}


def model_ok(dest: Path, sizes: dict | None = None) -> bool:
    if not (dest / "model.bin").is_file() or not (dest / "config.json").is_file():
        return False
    if (dest / "model.bin").stat().st_size < 10_000_000:
        return False
    for f, n in (sizes or {}).items():
        if n and (not (dest / f).is_file() or (dest / f).stat().st_size != n):
            return False
    return True


def _download_hf(name: str, dest: Path) -> bool:
    """Plano A: download do faster-whisper (sem o hf-xet, que trava em algumas redes), vigiado: se o tamanho
    baixado não muda por STALL_SECS, encerra e devolve False."""
    code = "import sys;from faster_whisper import download_model;download_model(sys.argv[1], output_dir=sys.argv[2])"
    env = dict(os.environ, HF_HUB_DISABLE_XET="1", HF_HUB_DISABLE_SYMLINKS_WARNING="1",
               HF_HUB_DISABLE_PROGRESS_BARS="1")
    p = subprocess.Popen([sys.executable, "-I", "-c", code, name, str(dest)], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    last, t_last, t_log = -1, time.time(), time.time()
    while p.poll() is None:
        time.sleep(3)
        size = _dir_size(dest)
        if size != last:
            last, t_last = size, time.time()
        if time.time() - t_log > 30:
            log(f"  baixando... {size / 1e6:.0f} MB")
            t_log = time.time()
        if time.time() - t_last > STALL_SECS:
            log(f"  download parado há {STALL_SECS} s em {size / 1e6:.0f} MB: tentando outro jeito")
            p.kill()
            return False
    return p.returncode == 0


def _download_direct(name: str, dest: Path) -> bool:
    """Plano B: baixa cada arquivo direto do Hugging Face (curl retoma de onde parou; sem curl, urllib)."""
    from faster_whisper.utils import _MODELS
    repo = _MODELS.get(name, name)
    sizes = _repo_files(repo)
    curl = which("curl")
    for f, n in sizes.items():
        out = dest / f
        if out.is_file() and (not n or out.stat().st_size == n):
            continue
        url = f"https://huggingface.co/{repo}/resolve/main/{f}"
        part = dest / (f + ".part")
        log(f"  baixando {f}" + (f" ({n / 1e6:.0f} MB)" if n else ""))
        if curl:
            r = subprocess.run([curl, "-sS", "-L", "--fail", "--retry", "5", "--retry-delay", "3", "-C", "-",
                                "--speed-limit", "1000", "--speed-time", str(STALL_SECS), "-o", str(part), url])
            if r.returncode != 0:
                return False
        else:
            from urllib.request import urlopen
            with urlopen(url, timeout=STALL_SECS) as src, open(part, "wb") as dst:
                while True:
                    buf = src.read(1 << 20)
                    if not buf:
                        break
                    dst.write(buf)
        if n and part.stat().st_size != n:
            log(f"  {f}: tamanho errado ({part.stat().st_size} de {n} bytes)")
            return False
        part.replace(out)
    return model_ok(dest, sizes)


def ensure_model(name: str):
    """Baixa o modelo para ~/.ai-stream-clipper/models/<nome>; a transcrição carrega dali, sem rede."""
    dest = model_dir(name)
    if model_ok(dest):
        return True, str(dest)
    dest.mkdir(parents=True, exist_ok=True)
    log(f"  downloading whisper model '{name}' (first time only)...")
    try:
        if _download_hf(name, dest) and model_ok(dest):
            return True, str(dest)
    except Exception as e:
        log(f"  download normal falhou: {str(e)[:160]}")
    try:
        log("  plano B: download direto dos arquivos")
        if _download_direct(name, dest):
            return True, str(dest)
    except Exception as e:
        return False, f"download falhou: {str(e)[:100]}"
    return False, "download falhou (confira a internet e rode o setup de novo; ele continua de onde parou)"


def install_ffmpeg():
    if IS_WIN and which("winget"):
        log("  installing ffmpeg with winget (Gyan.FFmpeg)...")
        subprocess.run(["winget", "install", "-e", "--id", "Gyan.FFmpeg", "--accept-source-agreements",
                        "--accept-package-agreements", "--silent"])
    elif IS_MAC and which("brew"):
        log("  installing ffmpeg with Homebrew...")
        subprocess.run(["brew", "install", "ffmpeg"])
    elif which("apt-get"):
        subprocess.run(["sudo", "apt-get", "install", "-y", "ffmpeg"])


def ffmpeg_features():
    ff = which("ffmpeg")
    if not ff:
        return None, False, []
    filters = run([ff, "-hide_banner", "-filters"], check=False).stdout
    has_ass = " ass " in filters
    encs = []
    tmp = Path(tempfile.gettempdir()) / "stream_clipper_enc_test.mp4"
    for enc in (["h264_nvenc"] if not IS_MAC else ["h264_videotoolbox"]) + ["libx264"]:
        r = run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30", "-t", "1",
                 "-c:v", enc, "-pix_fmt", "yuv420p", str(tmp)], check=False)
        if r.returncode == 0:
            encs.append(enc)
    try:
        tmp.unlink()
    except Exception:
        pass
    return ff, has_ass, encs


def test_gpu_whisper():
    add_cuda_dll_dirs()
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() == 0:
            return False, "no CUDA GPU"
    except Exception as e:
        return False, f"ctranslate2: {e}"
    ff = which("ffmpeg")
    wav = Path(tempfile.gettempdir()) / "stream_clipper_test.wav"
    run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=2", "-ar", "16000",
         "-ac", "1", str(wav)])
    code = ("import sys;sys.path.insert(0,sys.argv[1]);from cl_common import add_cuda_dll_dirs;"
            "add_cuda_dll_dirs();from faster_whisper import WhisperModel;"
            "m=WhisperModel('tiny',device='cuda',compute_type='float16');"
            "s,i=m.transcribe(sys.argv[2]);list(s);print('GPU_OK')")
    r = subprocess.run([sys.executable, "-I", "-c", code, str(Path(__file__).parent), str(wav)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "GPU_OK" in r.stdout:
        return True, "ok"
    return False, (r.stderr or "")[-300:]


def main(install: bool = True, force_cpu: bool = False, cookies_browser=None):
    log("AI Stream Clipper setup")
    log(f"  system: {platform.system()} {platform.release()}, python {sys.version.split()[0]}")
    rows = []
    ok_all = True
    if sys.version_info < (3, 9):
        rows.append(("python >= 3.9", False, sys.version.split()[0]))
        ok_all = False
    if is_store_python():
        log("")
        log("  Este é o Python da Microsoft Store. Ele instala os pacotes numa pasta do usuário que o")
        log("  `python -I` (modo seguro que a skill usa) ignora: eles sempre apareceriam como faltando.")
        if install and which("winget"):
            install_python_org()
            log("  Feche e abra o terminal (para o novo Python valer) e rode o setup de novo.")
        else:
            log("  Instale o Python em python.org marcando 'Add python.exe to PATH', feche e abra o")
            log("  terminal e rode o setup de novo.")
        log("")
        log("  [--] Python (não pode ser o da Microsoft Store)  " + sys.executable)
        log("")
        log("NOT READY. Python do python.org necessário.")
        return False
    # python packages
    missing = [pkg for mod, pkg in PIP.items() if not has_module(mod)]
    if install:
        # yt-dlp breaks when YouTube changes things: always update it
        pip_install(["yt-dlp[default]"] + [p for p in missing if not p.startswith("yt-dlp")])
        importlib.invalidate_caches()
    for mod, pkg in PIP.items():
        good = has_module(mod)
        rows.append((pkg, good, "" if good else "pip install " + pkg))
        if not good and mod not in OPTIONAL:
            ok_all = False
    # ffmpeg
    ff, has_ass, encs = ffmpeg_features()
    if (not ff or not has_ass) and install:
        install_ffmpeg()
        ff, has_ass, encs = ffmpeg_features()
    rows.append(("ffmpeg", bool(ff), ff or "not found"))
    rows.append(("ffmpeg libass (captions)", has_ass, "" if has_ass else "need an ffmpeg build with libass"))
    ok_all &= bool(ff) and has_ass
    encoder = encs[0] if encs else None
    rows.append(("video encoder", bool(encoder), encoder or "none"))
    ok_all &= bool(encoder)
    # JS runtime for YouTube
    js = which("deno") or which("node")
    if not js and install:
        if IS_WIN and which("winget"):
            subprocess.run(["winget", "install", "-e", "--id", "DenoLand.Deno", "--accept-source-agreements",
                            "--accept-package-agreements", "--silent"])
        elif IS_MAC and which("brew"):
            subprocess.run(["brew", "install", "deno"])
        js = which("deno") or which("node")
    rows.append(("JS runtime for YouTube (deno/node)", bool(js), js or "install deno: https://deno.com"))
    # leitura de áudio: PyAV compatível com o faster-whisper
    decode_ok = False
    if has_module("faster_whisper"):
        decode_ok, why = audio_decode_ok()
        if not decode_ok and install:
            log("  faster-whisper não consegue ler áudio com este PyAV: instalando av<17")
            pip_install(["av<17"])
            decode_ok, why = audio_decode_ok()
        rows.append(("audio decoding (PyAV)", decode_ok, "" if decode_ok else
                     f"pip install \"av<17\" ({why[0][:80]})"))
        ok_all &= decode_ok
    # GPU whisper
    device, compute, model = "cpu", "int8", "small"
    if not force_cpu and decode_ok:
        good, why = test_gpu_whisper()
        if not good and install and IS_WIN and ("cublas" in why.lower() or "cudnn" in why.lower()):
            pip_install(["nvidia-cublas-cu12", "nvidia-cudnn-cu12==9.*"])
            good, why = test_gpu_whisper()
        if good:
            device, compute, model = "cuda", "float16", "large-v3-turbo"
        rows.append(("NVIDIA GPU for transcription", good, "large-v3-turbo on GPU" if good else
                     f"CPU mode, model 'small' ({why.strip().splitlines()[-1][:80] if why.strip() else 'no GPU'})"))
    # whisper model download (pasta própria; a transcrição carrega dali sem rede)
    model_paths = dict(load_config().get("model_paths") or {})
    if has_module("faster_whisper") and install:
        good, where = ensure_model(model)
        rows.append((f"whisper model {model}", good, where))
        if good:
            model_paths[model] = where
        ok_all &= good
    elif model_ok(model_dir(model)):
        model_paths[model] = str(model_dir(model))
    rows.append(("face detector (YuNet)", YUNET.exists(), str(YUNET)))
    fonts_ok = (FONTS / "Montserrat-Black.ttf").exists()
    rows.append(("caption fonts (Cyrillic)", fonts_ok, ""))
    ok_all &= YUNET.exists() and fonts_ok
    cfg = load_config()
    cfg.update({"device": device, "compute_type": compute, "model": model, "cpu_model": "small",
                "encoder": encoder or "libx264", "model_paths": model_paths})
    if cookies_browser:
        cfg["cookies_from_browser"] = cookies_browser
    save_config(cfg)
    log("")
    for name, good, note in rows:
        log(f"  [{'OK' if good else '--'}] {name}{'  ' + note if note else ''}")
    log("")
    if ok_all:
        log(f"READY. Transcription on {device.upper()} ({model}), encoder {cfg['encoder']}.")
        log("Next: python -I scripts/clipper.py prepare <stream link>")
    else:
        log("NOT READY. Fix the [--] lines above (run setup again with --install).")
    return ok_all
