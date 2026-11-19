"""Acha lives (VODs) novas de GTA dos streamers em streamers.json que ainda não viraram cortes.

Uso (rode com python -I; precisa do yt-dlp que o "configura o clipper" instala):
  python -I clipper-gta-br/novas_lives.py              -> JSON com as lives pendentes (mais novas primeiro)
  python -I clipper-gta-br/novas_lives.py --verificar  -> testa se cada canal da lista responde
  python -I clipper-gta-br/novas_lives.py --marcar URL [--status ok|pulada|erro] [--nota TEXTO]
                                                       -> registra a live como processada
O histórico fica em ~/StreamClipper/processadas.json (nunca processa a mesma live duas vezes).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CONFIG = AQUI / "streamers.json"
ESTADO = Path.home() / "StreamClipper" / "processadas.json"


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
    """Página de lista de VODs do canal."""
    u = url.rstrip("/")
    if "twitch.tv" in u and "/videos" not in u:
        return u + "/videos?filter=archives&sort=time"
    if ("youtube.com/@" in u or "youtube.com/c/" in u or "youtube.com/channel/" in u) and not u.endswith("/streams"):
        return u + "/streams"
    if "kick.com" in u and "/videos" not in u:
        return u + "/videos"
    return u


def listar_videos(url: str, limite: int = 8) -> list:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "playlistend": limite,
            "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url_videos(url), download=False)
    return [e for e in (info.get("entries") or []) if e]


def link_do(e: dict) -> str:
    u = e.get("url") or e.get("webpage_url") or ""
    if u.startswith("http"):
        return u
    vid = str(e.get("id") or "")
    if vid.startswith("v") and vid[1:].isdigit():
        return f"https://www.twitch.tv/videos/{vid[1:]}"
    if vid.isdigit():
        return f"https://www.twitch.tv/videos/{vid}"
    return f"https://www.youtube.com/watch?v={vid}" if vid else u


def eh_gta(titulo: str, palavras) -> bool:
    t = (titulo or "").lower()
    return any(p.lower() in t for p in palavras)


def pendentes(cfg: dict, estado: dict, buscar=listar_videos) -> list:
    agora = time.time()
    limite_ts = agora - float(cfg.get("dias_para_tras", 3)) * 86400
    dur_min = float(cfg.get("duracao_minima_min", 30)) * 60
    palavras = cfg.get("palavras_gta", ["gta"])
    achadas = []
    for s in cfg.get("streamers", []):
        if not s.get("ativo", True):
            continue
        try:
            videos = buscar(s["url"])
        except Exception as e:  # um canal fora do ar não para os outros
            print(f"[aviso] {s['nome']}: {str(e)[:200]}", file=sys.stderr)
            continue
        for e in videos:
            link = link_do(e)
            if not link or link in estado:
                continue
            if e.get("live_status") == "is_live":
                continue  # ainda ao vivo: o VOD só serve quando a live acabar
            dur = float(e.get("duration") or 0)
            if dur and dur < dur_min:
                continue
            ts = e.get("timestamp") or e.get("release_timestamp")
            if ts and float(ts) < limite_ts:
                continue
            if s.get("so_gta") and not eh_gta(e.get("title", ""), palavras):
                continue
            achadas.append({"streamer": s["nome"], "url": link, "titulo": e.get("title", ""),
                            "duracao_min": round(dur / 60) if dur else None, "timestamp": ts,
                            "idioma": s.get("idioma", "pt"), "legenda": s.get("legenda") or cfg.get("legenda", "pt")})
    achadas.sort(key=lambda x: -(x["timestamp"] or 0))
    return achadas[: int(cfg.get("max_lives_por_rodada", 2))]


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verificar", action="store_true")
    ap.add_argument("--marcar", metavar="URL")
    ap.add_argument("--status", default="ok", choices=["ok", "pulada", "erro"])
    ap.add_argument("--nota", default="")
    a = ap.parse_args()

    cfg = ler_json(CONFIG, {})
    estado = ler_json(ESTADO, {})

    if a.marcar:
        estado[a.marcar] = {"status": a.status, "nota": a.nota, "quando": time.strftime("%Y-%m-%d %H:%M")}
        salvar_estado(estado)
        print(f"marcada: {a.marcar} ({a.status})")
        return 0

    if a.verificar:
        ok = True
        for s in cfg.get("streamers", []):
            try:
                v = listar_videos(s["url"], 1)
                print(f"[OK] {s['nome']}: {v[0].get('title', '?') if v else '(sem VODs públicos)'}")
            except Exception as e:
                ok = False
                print(f"[--] {s['nome']} ({s['url']}): {str(e)[:160]}")
        return 0 if ok else 1

    print(json.dumps(pendentes(cfg, estado), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
