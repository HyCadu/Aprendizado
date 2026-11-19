"""Acha vídeos novos de GTA dos canais em canais.json que ainda não viraram cortes.

Uso (rode com python -I; precisa do yt-dlp que o setup da skill instala):
  python -I cortes-youtube/novos_videos.py              -> JSON com os vídeos pendentes (mais novos primeiro)
  python -I cortes-youtube/novos_videos.py --link URL   -> confere um vídeo específico (duração, título,
                                                           se já foi cortado) e devolve no mesmo formato
  python -I cortes-youtube/novos_videos.py --verificar  -> testa se cada canal da lista responde
  python -I cortes-youtube/novos_videos.py --marcar URL [--status ok|pulado|erro] [--nota TEXTO]
O histórico fica em ~/CortesYouTube/processados.json (nunca corta o mesmo vídeo duas vezes no automático).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CONFIG = AQUI / "canais.json"
ESTADO = Path.home() / "CortesYouTube" / "processados.json"


def ler_json(p: Path, padrao):
    try:
        with open(p, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return padrao


def salvar_estado(estado: dict) -> None:
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ESTADO.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ESTADO)


def url_videos(url: str) -> str:
    u = url.rstrip("/")
    if "youtube.com/" in u and any(x in u for x in ("/@", "/c/", "/channel/", "/user/")) \
            and not u.endswith(("/videos", "/streams", "/shorts")):
        return u + "/videos"  # aba Vídeos: deixa Shorts e lives de fora
    return u


def ydl(opts_extra: dict):
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    opts.update(opts_extra)
    return yt_dlp.YoutubeDL(opts)


def listar_videos(url: str, limite: int = 10) -> list:
    with ydl({"extract_flat": "in_playlist", "playlistend": limite}) as y:
        info = y.extract_info(url_videos(url), download=False)
    return [e for e in (info.get("entries") or []) if e]


def info_video(url: str) -> dict:
    with ydl({}) as y:
        return y.extract_info(url, download=False)


def link_do(e: dict) -> str:
    u = e.get("webpage_url") or e.get("url") or ""
    if u.startswith("http"):
        return u
    vid = str(e.get("id") or "")
    return f"https://www.youtube.com/watch?v={vid}" if vid else u


def eh_gta(titulo: str, palavras) -> bool:
    t = (titulo or "").lower()
    return any(p.lower() in t for p in palavras)


def clipes_para(dur_seg: float, maximo: int) -> int:
    """Quantos clipes pedir, pela duração (mesma tabela do SKILL.md)."""
    m = (dur_seg or 0) / 60
    n = 2 if m < 10 else 3 if m < 20 else 4 if m < 40 else 5
    return max(1, min(maximo, n))


def item(nome: str, e: dict, maximo: int) -> dict:
    dur = float(e.get("duration") or 0)
    return {"canal": nome, "url": link_do(e), "titulo": e.get("title", ""),
            "duracao_min": round(dur / 60, 1) if dur else None, "clipes": clipes_para(dur, maximo),
            "timestamp": e.get("timestamp") or e.get("release_timestamp")}


def pendentes(cfg: dict, estado: dict, buscar=listar_videos) -> list:
    limite_ts = time.time() - float(cfg.get("dias_para_tras", 7)) * 86400
    dmin = float(cfg.get("duracao_minima_min", 3)) * 60
    dmax = float(cfg.get("duracao_maxima_min") or 0) * 60 or float("inf")   # 0 / vazio = sem limite
    palavras = cfg.get("palavras_gta", ["gta"])
    maximo = int(cfg.get("clipes_por_video", 5))
    achados = []
    for c in cfg.get("canais", []):
        if not c.get("ativo", True):
            continue
        try:
            videos = buscar(c["url"])
        except Exception as e:  # um canal fora do ar não para os outros
            print(f"[aviso] {c['nome']}: {str(e)[:200]}", file=sys.stderr)
            continue
        for e in videos:
            link = link_do(e)
            if not link or link in estado or e.get("live_status") in ("is_live", "is_upcoming"):
                continue
            dur = float(e.get("duration") or 0)
            if dur and not (dmin <= dur <= dmax):
                continue
            ts = e.get("timestamp") or e.get("release_timestamp")
            if ts and float(ts) < limite_ts:
                continue
            if c.get("so_gta") and not eh_gta(e.get("title", ""), palavras):
                continue
            achados.append(dict(item(c["nome"], e, maximo), legenda=c.get("legenda") or cfg.get("legenda", "pt")))
    achados.sort(key=lambda x: -(x["timestamp"] or 0))
    return achados[: int(cfg.get("max_videos_por_rodada", 2))]


def conferir_link(url: str, cfg: dict, estado: dict, buscar=info_video) -> dict:
    """Vídeo escolhido pelo usuário: não aplica filtro de canal/data/GTA, só avisa."""
    e = buscar(url)
    r = item(e.get("channel") or e.get("uploader") or "?", e, int(cfg.get("clipes_por_video", 5)))
    avisos = []
    dur = float(e.get("duration") or 0)
    if dur > 90 * 60:
        avisos.append(f"vídeo longo ({round(dur / 60)} min): a transcrição demora mais e a leitura é econômica (~40%)")
    if e.get("live_status") in ("is_live", "is_upcoming"):
        avisos.append("ainda ao vivo / agendado: espere terminar")
    if r["url"] in estado or url in estado:
        avisos.append("já foi cortado antes (vai cortar de novo)")
    r["avisos"] = avisos
    return r


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--link", action="append", metavar="URL", help="vídeo específico (pode repetir)")
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--marcar", metavar="URL")
    ap.add_argument("--status", default="ok", choices=["ok", "pulado", "erro"])
    ap.add_argument("--nota", default="")
    a = ap.parse_args()

    cfg = ler_json(CONFIG, {})
    estado = ler_json(ESTADO, {})

    if a.marcar:
        estado[a.marcar] = {"status": a.status, "nota": a.nota, "quando": time.strftime("%Y-%m-%d %H:%M")}
        salvar_estado(estado)
        print(f"marcado: {a.marcar} ({a.status})")
        return 0

    if a.link:
        saida = []
        for u in a.link:
            try:
                saida.append(conferir_link(u, cfg, estado))
            except Exception as e:
                saida.append({"url": u, "erro": str(e)[:300]})
        print(json.dumps(saida, ensure_ascii=False, indent=1))
        return 0 if all("erro" not in x for x in saida) else 1

    if a.verificar:
        ok = True
        for c in cfg.get("canais", []):
            try:
                v = listar_videos(c["url"], 1)
                print(f"[OK] {c['nome']}: {v[0].get('title', '?') if v else '(sem vídeos)'}")
            except Exception as e:
                ok = False
                print(f"[--] {c['nome']} ({c['url']}): {str(e)[:160]}")
        return 0 if ok else 1

    print(json.dumps(pendentes(cfg, estado), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
