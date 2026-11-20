"""Capa (thumbnail 1080x1920) de cada clipe: o quadro mais forte do clipe como fundo, editado (zoom, contraste,
cor e vinheta), dois outros momentos do clipe em cartões inclinados com borda neon, o hook em letras grandes
e a identidade visual (moldura neon + arroba). Sai em <clipe>_capa.jpg, ao lado do .mp4.

Tudo com ffmpeg + libass (o mesmo que o render já usa): os quadros passam pelo mesmo layout do clipe (facecam em
cima / gameplay embaixo ou 9:16), mas sem legenda nem hook."""
from __future__ import annotations

from pathlib import Path

from cl_captions import (EMOJI, HOOK_FONT, HOOK_FONT_FILE, HIGHLIGHT, ass_time, brand_events, censor, clean_handle,
                         esc, handle_box, text_width, wrap)
from cl_common import ffmpeg, run, write_text

COVER_SIZES = (150, 136, 122, 110, 96)  # tamanhos do título, do maior para o menor
COVER_MAX_W = 940                       # largura máxima de uma linha do título, px
CARD_W, CARD_H = 318, 566               # cartões dos momentos (9:16)
CARD_Y = 1250                           # topo dos cartões
CARD_TILT = 5                           # inclinação dos cartões, graus
NEON_HEX = "0xB026FF"                   # mesmo roxo da moldura (cl_captions.NEON)


def cover_times(dur: float, zooms=None) -> list:
    """Plano B, sem olhar os quadros: o principal (meio do trecho de narração mais forte, ou ~45% do clipe) e dois
    momentos espalhados para os cartões."""
    main = None
    if zooms:
        s, e = max(zooms, key=lambda z: z[1] - z[0])
        main = (s + e) / 2
    if main is None or not (0.3 < main < dur - 0.3):
        main = dur * 0.45
    others = []
    for f in (0.15, 0.8, 0.3, 0.65):
        t = dur * f
        if abs(t - main) > dur * 0.12 and all(abs(t - o) > dur * 0.12 for o in others):
            others.append(t)
        if len(others) == 2:
            break
    while len(others) < 2:
        others.append(dur * (0.2 if not others else 0.85))
    return [round(main, 2)] + [round(t, 2) for t in others]


SAMPLE_FPS = 10         # quadros lidos por segundo (para achar cortes de cena)
CAND_EVERY = 5          # candidato a capa a cada 5 quadros lidos (0,5 s)
CUT_DIFF = 22           # diferença média (0-255) entre ±0,2 s acima disto = corte de cena / movimento brusco
SW, SH = 160, 90        # tamanho da amostra (só para dar nota)


def frame_score(rgb):
    """Nota de um quadro para capa: None se for tela preta / lisa (loading, fade, transição). Premia detalhe (bordas),
    contraste e cor; tela de menu (texto cinza sobre fundo escuro) tem pouca cor e perde para a ação."""
    import numpy as np
    f = rgb.astype(np.float32)
    y = 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]
    m, sd = float(y.mean()), float(y.std())
    dark = float((y < 28).mean())
    if m < 30 or sd < 14 or dark > 0.6 or m > 235:
        return None
    edges = float(np.abs(np.diff(y, axis=0)).mean() + np.abs(np.diff(y, axis=1)).mean())
    rg = f[..., 0] - f[..., 1]
    yb = 0.5 * (f[..., 0] + f[..., 1]) - f[..., 2]
    color = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    return 0.5 * sd + 1.2 * edges + 0.8 * color - 25 * max(0.0, dark - 0.3)


def pick_times(section: Path, off: float, dur: float, lay: dict, zooms=None, mp4: Path | None = None) -> list:
    """Avalia um quadro a cada 0,5 s (fora de cortes de cena) e devolve [principal, cartão 1, cartão 2] em segundos do clipe: o principal é o
    melhor quadro, com bônus dentro dos trechos de narração forte; os cartões são os melhores seguintes, longe no
    tempo do principal e entre si. Lê o .mp4 já renderizado (rápido de decodificar), na área do gameplay e fora da
    faixa da legenda e do hook; sem ele, lê o trecho baixado. Cai no plano B (cover_times) se não der."""
    import subprocess
    import numpy as np
    from cl_common import video_stream
    use_mp4 = mp4 is not None and Path(mp4).is_file()
    try:
        if use_mp4:
            W, H, src, vf = 1080, 1920, Path(mp4), ""
        else:
            vs = video_stream(section)
            W, H, src = int(vs["width"]), int(vs["height"]), section
            vf = f"trim=start={off:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS,"
        sw, sh = (SH, SW) if use_mp4 else (SW, SH)    # amostra em pé para o mp4 vertical
        raw = subprocess.run([ffmpeg(), "-v", "error", "-i", str(src), "-an", "-vf",
                              f"{vf}fps={SAMPLE_FPS},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "rgb24",
                              "pipe:1"], capture_output=True, timeout=300).stdout
    except Exception:
        return cover_times(dur, zooms)
    n = len(raw) // (sw * sh * 3)
    if n < 4:
        return cover_times(dur, zooms)
    frames = np.frombuffer(raw[: n * sw * sh * 3], np.uint8).reshape(n, sh, sw, 3)
    rows = []

    def region_of(i, sg):
        if use_mp4:
            # gameplay = painel de baixo (facecam) ou o quadro todo; sem hook (topo), sem legenda (y 1100-1320)
            y_top = 740 if sg["mode"] == "facecam" else 420
            fr = frames[i]
            ys = lambda v: int(v / H * sh)
            return np.concatenate([fr[ys(y_top):ys(1100)], fr[ys(1320):ys(1880)]], axis=0)[:, 1:-1]
        x, y, w, h = sg["game"] if sg["mode"] == "facecam" else sg["full"]
        x0, y0 = int(x / W * sw), int(y / H * sh)
        x1, y1 = max(x0 + 4, int((x + w) / W * sw)), max(y0 + 4, int((y + h) / H * sh))
        return frames[i, y0:y1, x0:x1]

    for i in range(2, n - 2, CAND_EVERY):
        t = i / SAMPLE_FPS
        if t < 0.4 or t > dur - 0.4:
            continue
        sg = _seg_at(lay, t)
        # perto de um corte de cena o quadro pego no trecho pode ser o do outro lado (ou a transição): pula
        if np.abs(region_of(i - 2, sg).astype(np.int16) - region_of(i + 2, sg).astype(np.int16)).mean() > CUT_DIFF:
            continue
        region = region_of(i, sg)
        sc = frame_score(region)
        if sc is None:
            continue
        if zooms and any(s <= t <= e for s, e in zooms):
            sc *= 1.15
        rows.append((sc, t))
    if len(rows) < 3:
        return cover_times(dur, zooms)
    rows.sort(reverse=True)
    gap = max(1.5, dur * 0.15)
    chosen = []
    for need_gap in (gap, gap / 2, 0.6):
        for sc, t in rows:
            if len(chosen) == 3:
                break
            if all(abs(t - c) >= need_gap for c in chosen):
                chosen.append(t)
        if len(chosen) == 3:
            break
    if len(chosen) < 3:
        return cover_times(dur, zooms)
    main, c1, c2 = chosen
    c1, c2 = sorted((c1, c2))   # cartão da esquerda = momento mais cedo
    return [round(main, 2), round(c1, 2), round(c2, 2)]


def _seg_at(lay: dict, t: float) -> dict:
    for sg in lay["segments"]:
        if sg.get("t0", 0.0) <= t < sg.get("t1", 1e9):
            return sg
    return lay["segments"][-1]


def _frame_graph(seg: dict, src: str, dst: str, gameplay_only: bool) -> str:
    """Filtro que monta um quadro no layout do clipe (1080x1920). gameplay_only: no modo facecam, só o painel do
    gameplay em 9:16 (para os cartões, sem repetir o rosto que já está no fundo)."""
    from cl_render import _chain   # import tardio: cl_render importa este módulo
    if gameplay_only and seg["mode"] == "facecam":
        gx, gy, gw, gh = seg["game"]
        cw = min(gw, int(gh * 9 / 16)) // 2 * 2
        return f"[{src}]crop={cw}:{gh}:{gx + (gw - cw) // 2}:{gy},scale=1080:1920:flags=lanczos,setsar=1[{dst}]"
    return _chain(seg, src, dst)


def grab_frames(section: Path, off: float, times: list, lay: dict, outs: list):
    """Os quadros dos instantes `times` (s do clipe), numa chamada só. O trecho é AV1/VP9 1440p: decodificar desde o
    começo levava ~18 s por capa. Cada instante vira uma entrada que pula (-ss) para 3 s antes e corta com trim no
    tempo absoluto (-copyts): o -ss sozinho cai em outra cena nos trechos do yt-dlp, e o trim no tempo do container
    é o mesmo corte do render. O primeiro sai no layout do clipe; os outros, só o gameplay."""
    cmd, parts = [ffmpeg(), "-v", "error", "-y", "-copyts"], []
    for i, t in enumerate(times):
        cmd += ["-ss", f"{max(0.0, off + t - 3):.3f}", "-i", str(section)]
        parts.append(f"[{i}:v]trim=start={off + t:.3f},setpts=PTS-STARTPTS[n{i}]")
        parts.append(_frame_graph(_seg_at(lay, t), f"n{i}", f"v{i}", gameplay_only=i > 0))
    cmd += ["-filter_complex", ";".join(parts)]
    for i, o in enumerate(outs):
        cmd += ["-map", f"[v{i}]", "-frames:v", "1", str(o)]
    run(cmd)


def title_lines(hook: str):
    """Quebra o hook no maior tamanho que caiba em até 3 linhas. Retorna (linhas, tamanho)."""
    text = censor(EMOJI.sub("", hook or "").strip()).upper()
    if not text:
        return [], 0
    for size in COVER_SIZES:
        lines = wrap(text, size, COVER_MAX_W, HOOK_FONT_FILE)
        if len(lines) <= 3 and all(text_width(x, size, HOOK_FONT_FILE) <= COVER_MAX_W for x in lines):
            return lines, size
    size = COVER_SIZES[-1]
    return wrap(text, size, COVER_MAX_W, HOOK_FONT_FILE)[:3], size


def cover_ass(hook: str, brand: dict, out: Path, center_y: float = 900):
    """Título grande (branco, última linha amarela, contorno preto grosso, leve inclinação), uma faixa escura
    desfocada atrás dele, e a moldura neon + arroba."""
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Title,{HOOK_FONT},100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H20000000,0,0,0,0,100,100,1,0,1,12,8,5,"
        "30,30,0,1",
        "Style: Box,Arial,20,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H64000000,0,0,0,0,100,100,0,0,1,0,6,7,0,0,0,1",
        "Style: Brand,Montserrat ExtraBold,32,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,"
        "0,0,5,0,0,0,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    t0, t1 = ass_time(0), ass_time(5)
    hl, size = title_lines(hook)
    if hl:
        lh = size * 1.02
        bh = len(hl) * lh + 80
        # faixa escura desfocada (legibilidade sobre qualquer fundo)
        lines.append(f"Dialogue: 1,{t0},{t1},Box,,0,0,0,,{{\\an7\\pos(-40,{center_y - bh / 2:.0f})\\1c&H000000&"
                     f"\\1a&H60&\\bord0\\shad0\\blur40\\p1}}m 0 0 l 1160 0 l 1160 {bh:.0f} l 0 {bh:.0f}{{\\p0}}")
        y = center_y - (len(hl) - 1) * lh / 2
        for i, txt in enumerate(hl):
            color = HIGHLIGHT if i == len(hl) - 1 and len(hl) > 1 else "&H00FFFFFF&"
            pos = f"\\an5\\pos(540,{y + i * lh:.0f})\\fs{size}\\frz2"
            # halo neon desfocado atrás + texto com contorno preto grosso
            lines.append(f"Dialogue: 2,{t0},{t1},Title,,0,0,0,,{{{pos}\\1a&HFF&\\3c&HFF26B0&\\3a&H40&\\bord22"
                         f"\\shad0\\blur18}}{esc(txt)}")
            lines.append(f"Dialogue: 3,{t0},{t1},Title,,0,0,0,,{{{pos}\\1c{color}}}{esc(txt)}")
    lines += brand_events(brand or {}, 4)
    write_text(out, "\n".join(lines) + "\n")


def make_cover(job: Path, section: Path, off: float, dur: float, lay: dict, hook: str, out: Path,
               zooms=None, brand: dict | None = None, mp4: Path | None = None) -> Path:
    """Gera a capa do clipe em `out` (.jpg). Quadros temporários ficam em <pasta do clipe>/cover_*.png."""
    cdir = out.parent
    times = pick_times(section, off, dur, lay, zooms, mp4)
    pngs = [cdir / f"cover_{i}.png" for i in range(len(times))]
    grab_frames(section, off, times, lay, pngs)
    ass = cdir / "cover.ass"
    # título logo abaixo do painel da câmera no modo facecam (o rosto fica livre); no 9:16 um pouco acima do meio
    facecam = _seg_at(lay, times[0])["mode"] == "facecam"
    handle = clean_handle((brand or {}).get("handle"))
    center_y = 940 if facecam else 760
    if handle:
        center_y = max(center_y, handle_box(handle)[1] + 300)
    cover_ass(hook, brand or {}, ass, center_y)
    a = CARD_TILT
    card = (f"scale={CARD_W}:{CARD_H}:force_original_aspect_ratio=increase,crop={CARD_W}:{CARD_H},"
            f"eq=saturation=1.25:contrast=1.08,pad={CARD_W + 12}:{CARD_H + 12}:6:6:color={NEON_HEX},"
            f"pad={CARD_W + 20}:{CARD_H + 20}:4:4:color=black,format=rgba")
    graph = (
        # fundo: quadro principal com zoom de 5% (quase sem cortar o topo), mais contraste e cor, nitidez e vinheta
        "[0:v]scale=1134:2016:flags=lanczos,crop=1080:1920:27:24,"
        "eq=contrast=1.15:saturation=1.45:brightness=0.03:gamma=1.18,unsharp=5:5:0.7,vignette=angle=0.5[bg];"
        f"[1:v]{card},rotate=-{a}*PI/180:c=none:ow=rotw({a}*PI/180):oh=roth({a}*PI/180)[c1];"
        f"[2:v]{card},rotate={a}*PI/180:c=none:ow=rotw({a}*PI/180):oh=roth({a}*PI/180)[c2];"
        f"[bg][c1]overlay=36:{CARD_Y}[t1];[t1][c2]overlay=W-w-36:{CARD_Y + 20},format=yuv420p,"
        f"ass=filename={ass.relative_to(job).as_posix()}:fontsdir=fonts[v]")
    run([ffmpeg(), "-v", "error", "-y", "-i", str(pngs[0]), "-i", str(pngs[1]), "-i", str(pngs[2]),
         "-filter_complex", graph, "-map", "[v]", "-frames:v", "1", "-q:v", "2", str(out)], cwd=str(job))
    for p in pngs:
        p.unlink(missing_ok=True)
    return out
