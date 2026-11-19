"""Transcription on AMD / Intel GPUs (Windows): whisper.cpp built with Vulkan.

faster-whisper (CTranslate2) only runs on NVIDIA. whisper.cpp has no ready Vulkan build for Windows, so
setup --vulkan installs CMake, the Vulkan SDK and the VS C++ Build Tools with winget and compiles
whisper-cli once into ~/.ai-stream-clipper/whispercpp/.

Speech regions come from faster-whisper's Silero VAD (whisper.cpp's own --vad moves segment times back
to the original timeline but not word times). The speech is glued into one wav, whisper-cli transcribes
it with DTW word timestamps, and the word times are mapped back to the stream timeline here.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import tempfile
import urllib.request
import wave
from pathlib import Path

import numpy as np

from cl_common import CONFIG_DIR, IS_WIN, Timer, fmt_ts, load_config, log, which

TAG = "v1.9.5"
REPO = "https://github.com/ggml-org/whisper.cpp"
WCPP_DIR = CONFIG_DIR / "whispercpp"
SRC_DIR = WCPP_DIR / "src"
BUILD_DIR = WCPP_DIR / "build"
DTW_PRESET = {"large-v3-turbo": "large.v3.turbo", "large-v3": "large.v3", "medium": "medium",
              "small": "small", "base": "base", "tiny": "tiny"}
MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{}.bin"
WINGET_DEPS = [
    ("Kitware.CMake", []),
    ("KhronosGroup.VulkanSDK", []),
    ("Microsoft.VisualStudio.2022.BuildTools",
     ["--override", "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools "
                    "--includeRecommended"]),
]


# ---------- paths and detection ----------

def cli_path() -> Path | None:
    cfg = load_config()
    for p in (cfg.get("whispercpp_cli"), BUILD_DIR / "bin" / "Release" / "whisper-cli.exe",
              BUILD_DIR / "bin" / "whisper-cli.exe", BUILD_DIR / "bin" / "whisper-cli"):
        if p and Path(p).is_file():
            return Path(p)
    return None


def model_file(name: str) -> Path:
    return WCPP_DIR / f"ggml-{name}.bin"


def gpu_names() -> list[str]:
    if not IS_WIN:
        return []
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-CimInstance Win32_VideoController).Name"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]


def vulkan_gpu() -> str | None:
    """Name of an AMD Radeon / Intel Arc card, if any (NVIDIA uses the CUDA path)."""
    for n in gpu_names():
        if re.search(r"radeon|\bamd\b|intel.*\barc\b", n, re.I) and not re.search(r"radeon\(tm\) graphics$", n, re.I):
            return n
    return None


# ---------- install and build ----------

def _cmake() -> str | None:
    return which("cmake") or next(iter(glob.glob(r"C:\Program Files\CMake\bin\cmake.exe")), None)


def _vulkan_sdk() -> str | None:
    p = os.environ.get("VULKAN_SDK")
    if p and Path(p).is_dir():
        return p
    if IS_WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
            p = winreg.QueryValueEx(k, "VULKAN_SDK")[0]
            if p and Path(p).is_dir():
                return p
        except OSError:
            pass
        found = sorted(glob.glob(r"C:\VulkanSDK\*"))
        if found:
            return found[-1]
    return None


def _has_msvc() -> bool:
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / \
        "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if not vswhere.is_file():
        return False
    r = subprocess.run([str(vswhere), "-products", "*", "-requires",
                        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return bool(r.stdout.strip())


def build_tools_status() -> dict:
    return {"cmake": bool(_cmake()), "vulkan_sdk": bool(_vulkan_sdk()), "msvc": _has_msvc(),
            "git": bool(which("git"))}


def install_build_tools() -> None:
    st = build_tools_status()
    need = {"Kitware.CMake": not st["cmake"], "KhronosGroup.VulkanSDK": not st["vulkan_sdk"],
            "Microsoft.VisualStudio.2022.BuildTools": not st["msvc"]}
    for pkg, extra in WINGET_DEPS:
        if need[pkg]:
            log(f"  installing {pkg} with winget (Windows may ask for admin rights)...")
            subprocess.run(["winget", "install", "-e", "--id", pkg, "--silent", "--accept-source-agreements",
                            "--accept-package-agreements"] + extra)


def build() -> tuple[bool, str]:
    """Clone and compile whisper-cli with Vulkan. Returns (ok, message)."""
    cmake, sdk, git = _cmake(), _vulkan_sdk(), which("git")
    if not (cmake and sdk and git and _has_msvc()):
        return False, f"missing build tools: {build_tools_status()}"
    WCPP_DIR.mkdir(parents=True, exist_ok=True)
    if not (SRC_DIR / "CMakeLists.txt").is_file():
        log(f"  cloning whisper.cpp {TAG}...")
        r = subprocess.run([git, "clone", "--depth", "1", "-b", TAG, REPO, str(SRC_DIR)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return False, "git clone failed: " + r.stderr[-300:]
    env = dict(os.environ, VULKAN_SDK=sdk)
    env["PATH"] = str(Path(sdk) / "Bin") + os.pathsep + env.get("PATH", "")
    log("  compiling whisper.cpp with Vulkan (5-15 min, first time only)...")
    steps = [
        [cmake, "-S", str(SRC_DIR), "-B", str(BUILD_DIR), "-DGGML_VULKAN=ON", "-DWHISPER_BUILD_TESTS=OFF",
         "-DWHISPER_BUILD_SERVER=OFF", "-DWHISPER_SDL2=OFF", "-DBUILD_SHARED_LIBS=OFF"],
        [cmake, "--build", str(BUILD_DIR), "--config", "Release", "--target", "whisper-cli", "-j"],
    ]
    for cmd in steps:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            (WCPP_DIR / "build.log").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
            return False, f"build failed, see {WCPP_DIR / 'build.log'}"
    return (True, "ok") if cli_path() else (False, "whisper-cli not found after build")


def download_model(name: str) -> Path:
    dst = model_file(name)
    if dst.is_file() and dst.stat().st_size > 10_000_000:
        return dst
    WCPP_DIR.mkdir(parents=True, exist_ok=True)
    part = dst.with_suffix(".part")
    log(f"  downloading whisper.cpp model '{name}' (first time only)...")
    req = urllib.request.Request(MODEL_URL.format(name), headers={"User-Agent": "stream-clipper"})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    part.replace(dst)
    return dst


def test_gpu(model: str = "large-v3-turbo") -> tuple[bool, str]:
    """Run whisper-cli on 2 s of a tone; ok if it ran on a Vulkan device."""
    cli = cli_path()
    if not cli:
        return False, "whisper-cli not built"
    mf = model_file(model)
    if not mf.is_file():
        return False, f"model {mf.name} missing"
    wav = Path(tempfile.gettempdir()) / "stream_clipper_vk_test.wav"
    _write_wav(wav, (0.1 * np.sin(np.arange(32000) * 2 * np.pi * 300 / 16000)).astype(np.float32))
    r = subprocess.run([str(cli), "-m", str(mf), "-f", str(wav), "-l", "en", "-nt"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    err = (r.stderr or "") + (r.stdout or "")
    m = re.search(r"ggml_vulkan: 0 = ([^|(\n]+)", err)
    if r.returncode == 0 and m:
        return True, m.group(1).strip()
    return False, err.strip().splitlines()[-1][:120] if err.strip() else f"exit {r.returncode}"


# ---------- transcription ----------

def _write_wav(path: Path, audio: np.ndarray) -> None:
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())


def _speech_chunks(audio: np.ndarray):
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    # same defaults faster-whisper's batched pipeline uses for vad_filter=True
    return get_speech_timestamps(audio, VadOptions(max_speech_duration_s=30, min_silence_duration_ms=160))


class _TimeMap:
    """Speech-only timeline -> original timeline (like faster-whisper's SpeechTimestampsMap, in ms)."""

    def __init__(self, chunks, sr=16000):
        self.ends, self.offset = [], []
        prev_end, silence = 0, 0
        for c in chunks:
            silence += c["start"] - prev_end
            prev_end = c["end"]
            self.ends.append((c["end"] - silence) / sr)
            self.offset.append(silence / sr)

    def largest_piece(self, s: float, e: float) -> tuple[float, float]:
        """[s, e] on the glued timeline, cut at chunk seams; the longest piece."""
        import bisect
        cuts = [b for b in self.ends[bisect.bisect_right(self.ends, s):] if b < e]
        if not cuts:
            return s, e
        edges = [s] + cuts + [e]
        return max(zip(edges, edges[1:]), key=lambda p: p[1] - p[0])

    def orig(self, t: float, is_end=False) -> float:
        import bisect
        i = bisect.bisect_left(self.ends, t) if is_end else bisect.bisect_right(self.ends, t)
        return t + self.offset[min(i, len(self.offset) - 1)]


_PUNCT_ONLY = re.compile(r"^[\W_]+$", re.UNICODE)


def _segments_to_words(data: dict) -> list[tuple[str, list[dict]]]:
    """whisper.cpp tokens -> words, per segment. A token starting with a space starts a new word.
    t_dtw (centiseconds) marks where a token ENDS: word end = t_dtw of its last token, word start = t_dtw of
    the token before it (but not before the segment start). Measured against faster-whisper on a pt-BR
    GTA RP stream: median 18 ms off, 88 % of words within 120 ms. Without DTW: token offsets (rougher)."""
    out = []
    prev_end = 0.0
    for seg in data.get("transcription", []):
        seg_t0 = seg["offsets"]["from"] / 1000.0
        words = []
        for t in seg.get("tokens", []):
            if t["text"].startswith("[_"):
                continue
            dtw = t.get("t_dtw", -1)
            has_dtw = dtw is not None and dtw >= 0
            t1 = dtw / 100.0 if has_dtw else t["offsets"]["to"] / 1000.0
            t0 = max(prev_end, seg_t0) if has_dtw else t["offsets"]["from"] / 1000.0
            if t["text"].startswith(" ") or not words:
                words.append({"w": t["text"], "s": min(t0, t1), "e": t1, "ps": [t["p"]]})
            else:
                words[-1]["w"] += t["text"]
                words[-1]["e"] = max(words[-1]["e"], t1)
                words[-1]["ps"].append(t["p"])
            prev_end = t1
        clean = []
        for w in words:
            txt = w["w"].strip()
            if txt.startswith("- "):  # whisper.cpp marks speaker turns with "- "
                txt = txt[2:].strip()
            if not txt or _PUNCT_ONLY.match(txt):
                continue
            clean.append({"w": txt, "s": w["s"], "e": max(w["e"], w["s"] + 0.02), "p": float(min(w["ps"]))})
        text = re.sub(r"(^|\s)-\s+", r"\1", seg.get("text", "")).strip()
        out.append((text, clean))
    return out


BLOCK_SPEECH_S = 20 * 60  # speech per whisper-cli run: a crash costs one block, not the whole stream
TRIES = 3


def _blocks(chunks, max_s=BLOCK_SPEECH_S, sr=16000):
    blocks, cur, cur_len = [], [], 0
    for c in chunks:
        n = c["end"] - c["start"]
        if cur and cur_len + n > max_s * sr:
            blocks.append(cur)
            cur, cur_len = [], 0
        cur.append(c)
        cur_len += n
    if cur:
        blocks.append(cur)
    return blocks


def json_to_segments(data: dict, chunks) -> list[dict]:
    """whisper-cli JSON of the glued speech of `chunks` -> segments on the original timeline.
    A word that straddles a seam between two speech chunks would swallow the whole silence between them
    once mapped back (e.g. 'Calma,' 10007-10024 s, spoken at 10023.5): it keeps only its larger side."""
    tmap = _TimeMap(chunks)
    segs = []
    for text, words in _segments_to_words(data):
        for w in words:
            gs, ge = tmap.largest_piece(w["s"], w["e"])
            w["s"] = round(tmap.orig(gs), 3)
            w["e"] = round(tmap.orig(ge, is_end=True), 3)
            w["e"] = max(w["e"], w["s"] + 0.02)
        if words:
            segs.append({"s": words[0]["s"], "e": words[-1]["e"], "text": text, "words": words})
    return segs


def _run_cli(cmd, on_pct) -> tuple[int, list[str]]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                         errors="replace")
    tail = []
    for line in p.stdout:
        if line.startswith("["):  # transcript lines: not useful in an error log
            continue
        tail = (tail + [line])[-40:]
        m = re.search(r"progress\s*=\s*(\d+)%", line)
        if m:
            on_pct(int(m.group(1)))
    return p.wait(), tail


def transcribe(audio: np.ndarray, lang: str, model: str = "large-v3-turbo", workdir: Path | None = None,
               threads: int | None = None) -> list[dict]:
    """Returns segments: [{"s", "e", "text", "words": [{"s", "e", "w", "p"}]}] on the original timeline.
    The speech is transcribed in blocks of ~20 min; a block whose run fails (e.g. the GPU driver resets
    during a long job) is retried, and its error output is kept in <workdir>/whispercpp_error.log."""
    cli = cli_path()
    if not cli:
        raise RuntimeError("whisper-cli not built (run setup --vulkan)")
    mf = model_file(model)
    t = Timer()
    chunks = _speech_chunks(audio)
    if not chunks:
        return []
    total = sum(c["end"] - c["start"] for c in chunks)
    blocks = _blocks(chunks)
    log(f"  whisper.cpp: {total / 16000:.0f} s of speech in {len(audio) / 16000:.0f} s, {len(blocks)} block(s) "
        f"(VAD {t():.0f} s)")
    work = Path(workdir or tempfile.mkdtemp(prefix="wcpp_"))
    work.mkdir(parents=True, exist_ok=True)
    errlog = work / "whispercpp_error.log"
    threads = threads or max(2, min(8, (os.cpu_count() or 4) // 2))
    segs, done = [], 0
    state = {"last": -10}

    for bi, block in enumerate(blocks):
        n = sum(c["end"] - c["start"] for c in block)
        wav, outbase = work / f"speech_{bi:02d}.wav", work / f"whispercpp_{bi:02d}"
        _write_wav(wav, np.concatenate([audio[c["start"]:c["end"]] for c in block]))
        cmd = [str(cli), "-m", str(mf), "-f", str(wav), "-l", lang, "-ojf", "-of", str(outbase), "-np", "-pp",
               "-t", str(threads), "-mc", "64"]
        if model in DTW_PRESET:  # DTW word times; whisper.cpp turns DTW off when flash attention is on
            cmd += ["-dtw", DTW_PRESET[model], "-nfa"]

        def on_pct(p, done=done, n=n):
            pct = int(100 * (done + n * p / 100) / total)
            if pct >= state["last"] + 10:
                state["last"] = pct
                log(f"  whisper.cpp: {pct}% ({t():.0f} s)")

        for attempt in range(1, TRIES + 1):
            code, tail = _run_cli(cmd, on_pct)
            out = Path(str(outbase) + ".json")
            if code == 0 and out.is_file():
                break
            with open(errlog, "a", encoding="utf-8") as f:
                f.write(f"--- block {bi + 1}/{len(blocks)}, try {attempt}, exit code {code}\n{''.join(tail)}\n")
            log(f"  whisper.cpp: block {bi + 1}/{len(blocks)} failed (exit code {code}), "
                f"{'retrying' if attempt < TRIES else 'giving up'}; details in {errlog}")
        else:
            raise RuntimeError(f"whisper-cli failed {TRIES} times on block {bi + 1} (exit code {code}), "
                               f"see {errlog}")
        data = json.loads(out.read_text(encoding="utf-8", errors="replace"))
        segs += json_to_segments(data, block)
        try:
            wav.unlink()
        except OSError:
            pass
        done += n
    log(f"  whisper.cpp: done in {t():.0f} s")
    return segs
