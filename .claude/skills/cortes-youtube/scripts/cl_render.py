"""Render picked moments into vertical 1080x1920 clips + post texts + report."""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from cl_captions import build_ass
from cl_cover import make_cover
from cl_translate import load as load_translation, translated_words
from cl_common import (FONTS, Timer, ffmpeg, ffprobe, fmt_dur, fmt_ts, lang_strings, load_config, log,
                       read_json, run, slug, video_stream, write_json, write_text)
from cl_fetch import download_section
from cl_layout import BOT_H, OUT_H, OUT_W, TOP_H, plan

PAD = 4.0  # seconds of extra video downloaded around each clip


def _audio_start(path: Path) -> float:
    """start_time of the first audio stream on the container timeline (0 if unknown)."""
    try:
        r = subprocess.run([ffprobe(), "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=start_time", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        return float(r.stdout.strip().split()[0])
    except Exception:
        return 0.0


def _pcm(path: Path, start: float, dur: float, sr: int = 8000) -> np.ndarray:
    """Audio of [start, start+dur] on the CONTAINER timeline, sample-exact.
    Input-side -ss is not used: on yt-dlp sections the audio and video streams often start at different
    times and the demuxer seeks by video keyframes, so -ss before -i can land seconds away from `start`."""
    start = max(0.0, start)
    sa = _audio_start(path)
    cmd = [ffmpeg(), "-v", "error", "-i", str(path), "-t", f"{start + dur:.3f}",
           "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "pipe:1"]
    r = subprocess.run(cmd, capture_output=True)
    x = np.frombuffer(r.stdout, np.float32).copy()
    # sample 0 sits at container time sa: shift so that index 0 == container time `start`
    shift = int(round((start - sa) * sr))
    if shift >= 0:
        x = x[shift:]
    else:
        x = np.concatenate([np.zeros(-shift, np.float32), x])
    return x[: int(dur * sr)]


def align_section(job: Path, section: Path, guess_t0: float) -> tuple:
    """Find where the downloaded section starts inside the stream by matching its audio
    against the full audio track. Returns (t0_in_stream, confidence)."""
    sr = 8000
    probe_len = 20.0
    sec = _pcm(section, 1.0, probe_len, sr)
    if len(sec) < sr * 5:
        return guess_t0, 0.0
    w0 = max(0.0, guess_t0 - 20.0)
    ref = _pcm(job / "media" / "audio16k.wav", w0, probe_len + 60.0, sr)
    if len(ref) < len(sec):
        return guess_t0, 0.0
    a = sec - sec.mean()
    b = ref - ref.mean()
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    corr = np.fft.irfft(np.fft.rfft(b, n) * np.conj(np.fft.rfft(a, n)), n)[: len(b) - len(a) + 1]
    cs = np.concatenate([[0.0], np.cumsum(b.astype(np.float64) ** 2)])
    win = (cs[len(a):] - cs[:-len(a)])[: len(corr)]
    e = np.sqrt(np.maximum(win, 0) * float((a ** 2).sum())) + 1e-9
    nc = corr / e
    lag = int(np.argmax(nc))
    t0 = w0 + lag / sr - 1.0
    return t0, float(nc[lag])


SYNC_AUDIO_TOL = 0.04     # s: clip audio vs transcript (auto-fixed by re-encoding)
SYNC_CAPTION_TOL = 0.12   # s: on-screen word highlight vs its scheduled time (= the spoken word)


def _ass_secs(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def caption_sync_check(mp4: Path, ass: Path, fps: int = 25, bands=None) -> dict:
    """Measure, on the FINISHED video, when the yellow word highlight actually changes, and compare
    with when each caption event was scheduled (= the word's start in the transcript). Catches any
    timestamp mix-up between the cut and the subtitle filter. Returns lag (s, + = captions late)."""
    starts = []
    for ln in ass.read_text(encoding="utf-8").splitlines():
        if ln.startswith("Dialogue:") and ",Cap," in ln:
            starts.append(_ass_secs(ln.split(",")[1]))
    if len(starts) < 6:
        return {"status": "skipped", "reason": "too few caption words"}
    # faixa da legenda em cada trecho (logo abaixo da cam no modo facecam, embaixo sem cam): lê de y0 do mais
    # alto a y1 do mais baixo em 1/4 da escala e, em cada quadro, olha só a faixa daquele trecho
    bands = bands or [(0.0, 1e9, 1140, 1300)]
    ya, yb = min(b[2] for b in bands) // 4 * 4, -(-max(b[3] for b in bands) // 4) * 4
    W, H = 270, (yb - ya) // 4
    raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(mp4), "-vf",
                          f"fps={fps},crop=1080:{yb - ya}:0:{ya},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "pipe:1"], capture_output=True).stdout
    n = len(raw) // (W * H * 3)
    if n < fps * 3:
        return {"status": "skipped", "reason": "could not read frames"}
    f = np.frombuffer(raw[: n * W * H * 3], np.uint8).reshape(n, H, W, 3).astype(np.int16)
    yellow = (f[..., 0] > 200) & (f[..., 1] > 170) & (f[..., 2] < 110)        # #FFE600 highlight
    mask = np.zeros((n, H, 1), bool)
    for k in range(n):
        tk = k / fps
        b = next((b for b in bands if b[0] <= tk < b[1]), bands[-1])
        mask[k, max(0, (b[2] - ya) // 4):max(0, (b[3] - ya) // 4)] = True
    yellow &= mask
    change = np.concatenate([[0], (yellow[1:] ^ yellow[:-1]).sum((1, 2))]).astype(np.float64)
    change = np.maximum(0, change - np.median(change))
    st = np.array(starts)

    def score(lag):
        idx = np.round((st + lag) * fps).astype(int)
        idx = idx[(idx >= 1) & (idx < n - 1)]
        return float(np.mean([change[i - 1:i + 2].max() for i in idx])) if len(idx) else 0.0

    lags = np.arange(-3.0, 3.0001, 1.0 / fps)
    sc = np.array([score(L) for L in lags])
    best = int(np.argmax(sc))
    base = float(np.median(sc)) + 1e-9
    strength = float(sc[best] / base)
    lag = float(lags[best])
    if strength < 2.0:
        return {"status": "unclear", "lag": round(lag, 3), "strength": round(strength, 2)}
    ok = abs(lag) <= SYNC_CAPTION_TOL
    return {"status": "ok" if ok else "FAIL", "lag": round(lag, 3), "strength": round(strength, 2)}


def encoder_args(cfg: dict):
    enc = cfg.get("encoder", "libx264")
    if enc == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "19", "-b:v", "0",
                "-maxrate", "24M", "-bufsize", "48M", "-profile:v", "high", "-spatial-aq", "1"]
    if enc == "h264_videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-b:v", "14M", "-profile:v", "high"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-profile:v", "high"]


def out_fps(section: Path) -> str:
    vs = video_stream(section)
    try:
        n, d = vs.get("avg_frame_rate", "30/1").split("/")
        f = float(n) / float(d)
    except Exception:
        f = 30.0
    if 29 <= f <= 61:
        return vs.get("avg_frame_rate")
    return "30"


def _chain(lay: dict, src: str, dst: str) -> str:
    """Filter chain that turns one source segment into a 1080x1920 frame."""
    if lay["mode"] == "facecam":
        cx, cy, cw, ch = lay["cam"]
        gx, gy, gw, gh = lay["game"]
        sharpen = ",unsharp=5:5:0.45" if OUT_W / cw > 1.6 else ""
        return (f"[{src}]split=2[{src}c][{src}g];"
                f"[{src}c]crop={cw}:{ch}:{cx}:{cy},scale={OUT_W}:{TOP_H}:flags=lanczos{sharpen}[{src}t];"
                f"[{src}g]crop={gw}:{gh}:{gx}:{gy},scale={OUT_W}:{BOT_H}:flags=lanczos[{src}b];"
                f"[{src}t][{src}b]vstack=inputs=2,"
                f"drawbox=x=0:y={TOP_H - 3}:w={OUT_W}:h=6:color=black@1:t=fill,setsar=1[{dst}]")
    x, y, w, h = lay["full"]
    return f"[{src}]crop={w}:{h}:{x}:{y},scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1[{dst}]"


ZOOM = 1.12            # punch-in nos trechos de narração mais intensa (1 = desliga)
ZOOM_MAX_SHARE = 0.30  # no máximo 30% do clipe com zoom
ZOOM_MIN_SCORE = 1.5   # quanto acima da fala "normal" do clipe o trecho precisa estar (dB + bônus)


def speech_zooms(section: Path, off: float, dur: float, words, a: float, sr: int = 8000) -> list:
    """Trechos (segundos do clipe) em que o narrador fala mais alto / mais rápido que o normal do clipe.
    Frases = palavras com pausa < 0.4 s; nota = volume (dB acima da mediana das frases) + 0.5 x velocidade
    (palavras/s acima da mediana) + 1.5 se tem "!". As melhores acima de ZOOM_MIN_SCORE ganham zoom."""
    ws = sorted((max(0.0, w["s"] - a), min(dur, w["e"] - a), w.get("w", "")) for w in words
                if w["e"] - a > 0.05 and w["s"] - a < dur - 0.05)
    if len(ws) < 6:
        return []
    x = _pcm(section, off, dur, sr)
    hop = int(0.05 * sr)
    n = len(x) // hop
    if n < 40:
        return []
    db = 20 * np.log10(np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-6)
    phrases = []
    for s, e, t in ws:
        if phrases and s - phrases[-1][1] < 0.4 and e - phrases[-1][0] <= 4.0:
            phrases[-1][1] = max(phrases[-1][1], e)
            phrases[-1][2] += 1
            phrases[-1][3] += t.count("!")
        else:
            phrases.append([s, e, 1, t.count("!")])
    rows = []
    for s, e, cnt, excl in phrases:
        if e - s < 0.6:
            continue
        seg = db[int(s / 0.05): max(int(s / 0.05) + 1, int(e / 0.05))]
        if len(seg):
            rows.append((s, e, float(np.percentile(seg, 90)), cnt / (e - s), excl))
    if len(rows) < 3:
        return []
    med_l = float(np.median([r[2] for r in rows]))
    med_r = float(np.median([r[3] for r in rows]))
    # volume pesa mais; velocidade ajuda; "!" (o Whisper marca grito/exclamação) dá um bônus
    scored = sorted(((r[2] - med_l) + 0.5 * (r[3] - med_r) + (1.5 if r[4] else 0.0), r[0], r[1])
                    for r in rows)[::-1]
    picked, used = [], 0.0
    for sc, s, e in scored:
        if sc < ZOOM_MIN_SCORE or used + (e - s) > ZOOM_MAX_SHARE * dur:
            continue
        picked.append([max(0.0, s - 0.05), min(dur, e + 0.25)])
        used += e - s
    picked.sort()
    merged = []
    for s, e in picked:                  # zooms quase colados viram um só (sem pisca-pisca)
        if merged and s - merged[-1][1] < 0.8:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [[round(s, 2), round(e, 2)] for s, e in merged]


def zoom_chain(lay: dict, zooms: list, src: str, z: float) -> tuple:
    """Punch-in nas janelas `zooms`: no modo facecam só a câmera (painel de cima) aproxima; nos outros, o quadro
    inteiro. A legenda e o hook entram depois (filtro ass), então não são afetados."""
    if not zooms or z <= 1.0:
        return "", src
    segs = lay["segments"]

    def mode_at(t):
        for sg in segs:
            if sg.get("t0", 0.0) <= t < sg.get("t1", 1e9):
                return sg["mode"]
        return segs[-1]["mode"]

    regions = {}
    for s, e in zooms:
        regions.setdefault("cam" if mode_at((s + e) / 2) == "facecam" else "full", []).append((s, e))
    parts, cur = [], src
    for i, (reg, wins) in enumerate(sorted(regions.items())):
        H = TOP_H if reg == "cam" else OUT_H
        cw, ch = int(OUT_W / z) // 2 * 2, int(H / z) // 2 * 2
        cx, cy = (OUT_W - cw) // 2, int((H - ch) * 0.42)   # um pouco acima do centro: rosto / ação
        en = "+".join(f"between(t,{s:.2f},{e:.2f})" for s, e in wins)
        parts.append(f"[{cur}]split=2[zb{i}][zs{i}];"
                     f"[zs{i}]crop={cw}:{ch}:{cx}:{cy},scale={OUT_W}:{H}:flags=lanczos[zi{i}];"
                     f"[zb{i}][zi{i}]overlay=0:0:enable='{en}'[zo{i}]")
        cur = f"zo{i}"
    return ";".join(parts), cur


def filter_graph(lay: dict, ass_rel: str, zooms=None, z: float = ZOOM) -> str:
    tail = f"format=yuv420p,ass=filename={ass_rel}:fontsdir=fonts[v]"
    segs = lay["segments"]
    if len(segs) == 1:
        parts, last = [f"[0:v]null[s0]", _chain(segs[0], "s0", "o0")], "o0"
    else:
        parts = [f"[0:v]split={len(segs)}" + "".join(f"[i{k}]" for k in range(len(segs)))]
        for k, sg in enumerate(segs):
            parts.append(f"[i{k}]trim=start={sg['t0']:.3f}:end={sg['t1']:.3f},setpts=PTS-STARTPTS[s{k}]")
            parts.append(_chain(sg, f"s{k}", f"o{k}"))
        parts.append("".join(f"[o{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[cat]")
        last = "cat"
    zc, last = zoom_chain(lay, zooms or [], last, z)
    if zc:
        parts.append(zc)
    parts.append(f"[{last}]{tail}")
    return ";".join(parts)


def contact_sheet(mp4: Path, out: Path, dur: float):
    run([ffmpeg(), "-v", "error", "-y", "-i", str(mp4), "-vf",
         f"fps=12/{dur:.2f},scale=270:480,tile=6x2:padding=6:color=white", "-frames:v", "1",
         "-q:v", "3", str(out)])


def post_texts(pick: dict, meta: dict, lang: str) -> dict:
    s = lang_strings(lang)
    tags = [t if t.startswith("#") else "#" + t for t in (pick.get("hashtags") or [])]
    tags = [t.replace(" ", "") for t in tags if len(t) > 1]
    for t in s["default_tags"]:
        if len(tags) >= 6:
            break
        if t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    credit = s["credit"].format(channel=meta.get("channel") or "?") if meta.get("channel") else ""
    src = s["credit_src"].format(url=meta["url"]) if meta.get("url") else ""
    cap = (pick.get("caption") or "").strip()
    title = (pick.get("title") or pick.get("hook") or "").strip()
    shorts_title = title if len(title) <= 95 else title[:92].rstrip() + "..."
    out = {
        "youtube_shorts": {"title": shorts_title,
                           "description": "\n\n".join(x for x in [cap, credit, src, " ".join(tags[:4] + [s["shorts_tag"]])] if x)},
        "tiktok": {"caption": " ".join(x for x in [cap, credit, " ".join(tags[:5])] if x)},
        "instagram_reels": {"caption": "\n\n".join(x for x in [cap, credit, " ".join(tags[:5])] if x)},
    }
    x_tags = " ".join(tags[:2])
    room = 280 - len(x_tags) - 2
    x_text = cap if len(cap) <= room else cap[: room - 3].rstrip() + "..."
    out["x"] = {"post": f"{x_text}\n\n{x_tags}".strip()}
    return out


def post_markdown(p: dict, pt: dict, clip_name: str) -> str:
    return "\n".join([
        f"# {clip_name}", "",
        f"Hook: {p.get('hook', '')}", f"Moment: {fmt_ts(p['start'])} - {fmt_ts(p['end'])}, score {p.get('score')}",
        f"Why: {p.get('why', '')}", "",
        "## YouTube Shorts", f"Title: {pt['youtube_shorts']['title']}", "", pt["youtube_shorts"]["description"], "",
        "## TikTok", pt["tiktok"]["caption"], "",
        "## Instagram Reels", pt["instagram_reels"]["caption"], "",
        "## X", pt["x"]["post"], "",
    ])


def manual_layout(box: str, W: int, H: int) -> dict:
    """--facecam x:y:w:h (source pixels): use this webcam box for every clip.
    --facecam full:X : no webcam (IRL, talk show) - one 9:16 crop of the whole frame centred on source x = X
    (use it when detection followed the wrong person or a face in a picture)."""
    if box.startswith("full:"):
        cw = int(H * OUT_W / OUT_H) // 2 * 2
        x0 = int(min(max(float(box[5:]) - cw / 2, 0), W - cw)) // 2 * 2
        return {"mode": "fullcam", "full": [x0, 0, cw, H // 2 * 2], "face_presence": 1.0, "t0": 0.0}
    from cl_layout import fit_aspect
    x, y, w, h = [float(v) for v in box.split(":")]
    cam = fit_aspect([x, y, x + w, y + h], OUT_W / TOP_H, (x + w / 2, y + h * 0.45), [0, 0, W, H])
    gh = H
    gw = gh * OUT_W / BOT_H
    gx = (W - gw) / 2
    if gx < x + w and gx + gw > x:  # move the gameplay crop away from the cam
        gx = x + w if x + w + gw <= W else max(0, x - gw)
    seg = {"mode": "facecam", "cam": [int(v) // 2 * 2 for v in cam], "game": [int(gx), 0, int(gw) // 2 * 2, int(gh) // 2 * 2],
           "face_presence": 1.0, "t0": 0.0}
    return seg


def render_job(job: Path, cookies=None, cookies_file=None, only=None, facecam=None, censor=True,
               caption_lead=0.0, original_captions=False, zoom=ZOOM, brand=True, cover=True) -> dict:
    t = Timer()
    meta = read_json(job / "job.json")
    meta.setdefault("timings", {})["render_started"] = time.time()
    write_json(job / "job.json", meta)
    chk = read_json(job / "moments.checked.json")
    if not chk:
        raise SystemExit("Run `check` first: moments.checked.json is missing")
    words = read_json(job / "transcript" / "words.json", [])
    lang = meta.get("language", "en")
    cfg = load_config()
    # identidade visual (moldura neon + arroba): config "brand" em ~/.ai-stream-clipper/config.json,
    # igual para as duas skills; ligada por padrão, --no-brand desliga neste render
    brand_cfg = {"frame": False, "handle": ""} if not brand else {"frame": True, "handle": "", **(cfg.get("brand") or {})}
    if brand_cfg.get("frame") or brand_cfg.get("handle"):
        log(f"  marca: moldura {'sim' if brand_cfg.get('frame') else 'não'}, arroba {brand_cfg.get('handle') or '-'}")
    fonts = job / "fonts"
    fonts.mkdir(exist_ok=True)
    for f in FONTS.glob("*.ttf"):
        if not (fonts / f.name).exists():
            shutil.copy2(f, fonts / f.name)
    clips_dir = job / "clips"
    results, todo = [], []
    picks = sorted(chk["picks"], key=lambda q: q["order"])
    # translated captions (translation.json written by Claude after `translate`), unless turned off
    tr = {} if original_captions else load_translation(job, [p for p in picks if not only or p["order"] in only])
    tr_lines = tr.get("lines", {}) if tr else {}
    cap_lang = tr.get("to", lang) if tr_lines else lang
    if tr_lines:
        log(f"  captions: translated to {cap_lang} (translation.json)")
    # pass 1: fetch the minutes we need, sync them, plan the layout
    for p in picks:
        k = p["order"]
        if only and k not in only:
            continue
        name = f"{k:02d}_{slug(p.get('title') or p.get('hook') or 'clip', 36)}"
        cdir = clips_dir / name
        cdir.mkdir(parents=True, exist_ok=True)
        a, b = p["start"], p["end"]
        dur = b - a
        log(f"  clip {k}: {fmt_ts(a)} - {fmt_ts(b)} ({dur:.1f} s)")
        try:
            ct = Timer()
            if meta["kind"] == "file":
                section, t0, conf = Path(meta["path"]), 0.0, 1.0
            else:
                sec_stem = job / "media" / "sections" / f"sec_{int(a)}_{int(b)}"
                sec_stem.parent.mkdir(parents=True, exist_ok=True)
                section = download_section(job, meta, a - PAD, b + PAD, sec_stem, cookies, cookies_file)
                t0, conf = align_section(job, section, a - PAD)
                if conf < 0.3:
                    log(f"    sync: low confidence ({conf:.2f}), using the requested cut time")
                    t0 = a - PAD
            off = max(0.0, a - t0)
            if facecam:
                vs = video_stream(section)
                seg = manual_layout(facecam, int(vs["width"]), int(vs["height"]))
                seg["t1"] = round(dur, 3)
                lay = {"segments": [seg], "mode": seg["mode"] + "(manual)", "face_presence": 1.0}
            else:
                lay = plan(section, off, dur, cdir / "layout_debug.jpg")
            todo.append(dict(p=p, k=k, name=name, cdir=cdir, section=section, off=off, dur=dur, conf=conf,
                             lay=lay, secs=ct()))
        except Exception as e:
            log(f"    FAILED: {str(e)[:400]}")
            results.append({"order": k, "name": name, "error": str(e)[:1000]})
    # the streamer's cam sits in the same place in most clips of one stream: if a clip picked
    # another face (a guest cam, a face in the video being watched), re-plan it with that prior
    if not facecam and len(todo) >= 2:
        centers = [(sg["face_center"], sg["t1"] - sg["t0"]) for x in todo for sg in x["lay"]["segments"]
                   if sg["mode"] == "facecam" and "face_center" in sg]
        best, best_w = None, 0
        for c, _ in centers:
            wsum = sum(d for c2, d in centers if abs(c2[0] - c[0]) < 0.08 and abs(c2[1] - c[1]) < 0.12)
            if wsum > best_w:
                best, best_w = c, wsum
        if best:
            for x in todo:
                off_prior = [sg for sg in x["lay"]["segments"] if sg["mode"] == "facecam" and "face_center" in sg
                             and (abs(sg["face_center"][0] - best[0]) > 0.08 or abs(sg["face_center"][1] - best[1]) > 0.12)]
                if off_prior:
                    log(f"    clip {x['k']}: cam differs from the other clips, re-checking")
                    x["lay"] = plan(x["section"], x["off"], x["dur"], x["cdir"] / "layout_debug.jpg", prior=best)
            # a clip that came out with NO cam while the other clips of this video have it in the same place
            # (calm streamer, small cam): look again for a live face right there
            with_cam = sum(1 for x in todo if any(sg["mode"] == "facecam" and "face_center" in sg
                                                  and abs(sg["face_center"][0] - best[0]) <= 0.08
                                                  and abs(sg["face_center"][1] - best[1]) <= 0.12
                                                  for sg in x["lay"]["segments"]))
            if with_cam >= 2 and with_cam * 2 >= len(todo):
                for x in todo:
                    if any(sg["mode"] == "facecam" for sg in x["lay"]["segments"]):
                        continue
                    log(f"    clip {x['k']}: no cam found, but the other clips have it - re-checking at that spot")
                    dbg = x["cdir"] / "layout_debug_retry.jpg"
                    lay2 = plan(x["section"], x["off"], x["dur"], dbg, prior=best, trust_prior=True)
                    if any(sg["mode"] == "facecam" for sg in lay2["segments"]):
                        x["lay"] = lay2
                        dbg.replace(x["cdir"] / "layout_debug.jpg")
                        log(f"    clip {x['k']}: cam found ({lay2['mode']})")
                    else:
                        dbg.unlink(missing_ok=True)
    # pass 2: captions + encode
    for x in todo:
        p, k, name, cdir, section, off, dur, conf, lay = (x[q] for q in ("p", "k", "name", "cdir", "section", "off",
                                                                        "dur", "conf", "lay"))
        a, b = p["start"], p["end"]
        ct = Timer()
        try:
            log(f"  clip {k}: layout {lay['mode']} (face in {int(lay['face_presence'] * 100)}% of frames)")
            ass = cdir / "captions.ass"
            wsel = [w for w in words if w["e"] > a and w["s"] < b]
            if k in tr_lines:
                wsel = translated_words(wsel, tr_lines[k])
            cap_info = build_ass(wsel, a, b, p.get("hook", ""), ass, lay["segments"], censor_on=censor,
                      lead=caption_lead, brand=brand_cfg)
            mp4 = cdir / f"{name}.mp4"
            rel_ass = ass.relative_to(job).as_posix()
            zooms = []
            if zoom > 1.0:
                try:
                    zooms = speech_zooms(section, off, dur, [w for w in words if w["e"] > a and w["s"] < b], a)
                except Exception as ze:
                    log(f"    zoom: skipped ({str(ze)[:120]})")
                log(f"    zoom: {len(zooms)} trecho(s) de narração forte" if zooms else "    zoom: nenhum trecho")
            fg = filter_graph(lay, rel_ass, zooms, zoom)
            fade_out = max(0.0, dur - 0.15)
            af = f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.06,afade=t=out:st={fade_out:.2f}:d=0.15"
            def encode(seek):
                # Cut with trim/atrim on the container timeline (the one _pcm/align_section use) and reset
                # both clocks to 0, so the captions (timed from 0) line up. -ss before -i seeks by video
                # keyframe and lands seconds off on yt-dlp sections; -ss after -i keeps the source
                # timestamps inside the filters, so the ass filter shows captions `seek` seconds late.
                cut_v = f"[0:v]trim=start={seek:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS[vin];"
                cut_a = f"atrim=start={seek:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS,"
                graph = cut_v + fg.replace("[0:v]", "[vin]", 1)
                tail = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-af", cut_a + af, "-movflags", "+faststart",
                        str(mp4)]
                base = [ffmpeg(), "-v", "error", "-y", "-i", str(section), "-t", f"{dur:.3f}",
                        "-filter_complex", graph, "-map", "[v]", "-map", "0:a:0", "-r", out_fps(section)]
                try:
                    run(base + encoder_args(cfg) + tail, cwd=str(job))
                except RuntimeError:
                    if cfg.get("encoder", "libx264") != "libx264":
                        log("    hardware encoder failed, retrying with libx264")
                        run(base + encoder_args({"encoder": "libx264"}) + tail, cwd=str(job))
                    else:
                        raise

            encode(off)
            # sync criterion, part 1: the clip's audio (the speech) must start where the transcript says
            sync = {"audio": {"status": "skipped"}}
            if meta["kind"] != "file" and conf >= 0.3:
                t_out, c_out = align_section(job, mp4, a)
                drift = t_out - a
                if c_out >= 0.5 and abs(drift) > SYNC_AUDIO_TOL:
                    log(f"    sync: speech was {drift * 1000:+.0f} ms off the captions, re-encoding")
                    off = max(0.0, off - drift)
                    encode(off)
                    t_out, c_out = align_section(job, mp4, a)
                    drift = t_out - a
                if c_out >= 0.5:
                    sync["audio"] = {"status": "ok" if abs(drift) <= SYNC_AUDIO_TOL else "FAIL",
                                     "drift": round(drift, 3), "conf": round(c_out, 2)}
                else:
                    sync["audio"] = {"status": "unclear", "conf": round(c_out, 2)}
            # part 2: each word must light up on screen at its scheduled (spoken) time
            sync["captions"] = caption_sync_check(mp4, ass, bands=cap_info.get("bands"))
            sa, sc_ = sync["audio"], sync["captions"]
            log(f"    sync: speech {sa['status']}" + (f" ({sa['drift'] * 1000:+.0f} ms)" if "drift" in sa else "")
                + f", captions {sc_['status']}" + (f" ({sc_['lag'] * 1000:+.0f} ms)" if "lag" in sc_ else ""))
            sync["status"] = "FAIL" if "FAIL" in (sa["status"], sc_["status"]) else (
                "ok" if sa["status"] == "ok" and sc_["status"] == "ok" else "check")
            contact_sheet(mp4, cdir / "sheet.jpg", dur)
            capa = None
            if cover:
                try:
                    capa = make_cover(job, section, off, dur, lay, p.get("hook") or p.get("title") or "",
                                      cdir / f"{name}_capa.jpg", zooms, brand_cfg, mp4)
                    log(f"    capa: {capa.name}")
                except Exception as ce:
                    log(f"    capa: falhou ({str(ce)[:200]})")
            pt =post_texts(p, meta, cap_lang if k in tr_lines else lang)   # crédito e tags no idioma da legenda
            write_json(cdir / "post.json", pt)
            write_text(cdir / "post.md", post_markdown(p, pt, name))
            secs = round(x["secs"] + ct(), 1)
            write_json(cdir / "clip.json", {"pick": p, "layout": lay, "captions_lang": cap_lang if k in tr_lines else lang,
                                            "sync_confidence": round(conf, 3), "zooms": zooms,
                                            "section_offset": round(off, 3), "sync": sync, "seconds": secs})
            results.append({"order": k, "name": name, "mp4": str(mp4), "sheet": str(cdir / "sheet.jpg"),
                            **({"cover": str(capa)} if capa else {}), "post": str(cdir / "post.md"), "start": a, "end": b, "duration": round(dur, 1),
                            "score": p.get("score"), "hook": p.get("hook"), "layout": lay["mode"], "seconds": secs,
                            "sync": sync})
            log(f"    done -> {mp4}")
        except Exception as e:
            log(f"    FAILED: {str(e)[:400]}")
            results.append({"order": k, "name": name, "error": str(e)[:1000]})
    results.sort(key=lambda r: r["order"])
    meta = read_json(job / "job.json")
    tm = meta.setdefault("timings", {})
    tm["render_finished"] = time.time()
    tm["render_sec"] = round(t(), 1)
    meta["clips"] = results
    meta["candidates_total"] = chk.get("candidates_total")
    write_json(job / "job.json", meta)
    write_report(job)
    return meta


def write_report(job: Path):
    meta = read_json(job / "job.json")
    tm = meta.get("timings", {})
    clips = meta.get("clips", [])
    ok = [c for c in clips if "mp4" in c]
    total = None
    if tm.get("prepare_started") and tm.get("render_finished"):
        total = tm["render_finished"] - tm["prepare_started"]
    pick_sec = None
    if tm.get("prepare_finished") and tm.get("render_started"):
        pick_sec = tm["render_started"] - tm["prepare_finished"]
    rep = {
        "title": meta.get("title"), "channel": meta.get("channel"), "url": meta.get("url") or meta.get("path"),
        "stream_length": fmt_ts(meta.get("duration", 0)), "stream_seconds": meta.get("duration"),
        "language": meta.get("language"), "candidates_found": meta.get("candidates_total"),
        "clips_kept": len(ok), "clips_failed": len(clips) - len(ok),
        "prepare_seconds": tm.get("prepare_sec"), "transcribe_seconds": tm.get("transcribe_sec"),
        "picking_seconds": round(pick_sec, 1) if pick_sec else None,
        "render_seconds": tm.get("render_sec"), "total_seconds": round(total, 1) if total else None,
        "clips": clips,
    }
    write_json(job / "report.json", rep)
    lines = [f"# {rep['title']}", "",
             f"- Channel: {rep['channel']}", f"- Source: {rep['url']}",
             f"- Stream length: {rep['stream_length']}", f"- Language: {rep['language']}",
             f"- Candidates found: {rep['candidates_found']}", f"- Clips kept: {rep['clips_kept']}",
             f"- Prepare (download + transcript + signals): {fmt_dur(rep['prepare_seconds'] or 0)}",
             f"- Picking (Claude reading the chunks): {fmt_dur(rep['picking_seconds'] or 0)}",
             f"- Render: {fmt_dur(rep['render_seconds'] or 0)}",
             f"- Total: {fmt_dur(rep['total_seconds'] or 0)}", "", "## Clips"]
    for c in clips:
        if "mp4" in c:
            sy = c.get("sync") or {}
            sa, sc_ = sy.get("audio", {}), sy.get("captions", {})
            sync_txt = (f"sync {sy.get('status', '?')}: speech {sa.get('status', '?')}"
                        + (f" {sa['drift'] * 1000:+.0f} ms" if "drift" in sa else "")
                        + f", captions {sc_.get('status', '?')}"
                        + (f" {sc_['lag'] * 1000:+.0f} ms" if "lag" in sc_ else ""))
            lines += [f"{c['order']}. {c['hook']} ({fmt_ts(c['start'])}, {c['duration']} s, score {c['score']}, "
                      f"{c['layout']})", f"   {c['mp4']}", f"   {sync_txt}"]
        else:
            lines += [f"{c['order']}. FAILED: {c.get('error', '')[:200]}"]
    write_text(job / "report.md", "\n".join(lines) + "\n")
