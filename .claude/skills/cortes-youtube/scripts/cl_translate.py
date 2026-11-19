"""Translated captions (e.g. an English video with pt-BR captions).

Flow:
  1. `clipper.py translate JOB` splits the speech of every checked pick into short phrases with exact
     times and writes `translate.md` (to read) + `translation.todo.json` (template).
  2. Claude writes `translation.json`: one translated line per phrase, same order and count.
  3. `render` sees translation.json and burns the translated captions: each phrase is on screen exactly
     while the original phrase is spoken; its words light up spread over that time (by length).
"""
from __future__ import annotations

import re
from pathlib import Path

from cl_common import fmt_ts, read_json, write_json, write_text

END = (".", "!", "?", "…")
GAP_SPLIT = 0.7      # silence that always starts a new phrase (s)
MAX_WORDS = 14
MAX_SECS = 5.0
LANG_NAMES = {"pt": "português do Brasil (pt-BR)", "en": "English", "es": "español", "ru": "русский"}


def clip_words(words, a, b):
    return [w for w in words if w["e"] > a and w["s"] < b]


def phrases(ws):
    """Split the clip's words into short phrases: sentence end, long pause, or too long."""
    out, cur = [], []
    for w in ws:
        if cur:
            prev = cur[-1]
            gap = w["s"] - prev["e"]
            pw = prev["w"].rstrip()
            span = w["e"] - cur[0]["s"]
            if (pw.endswith(END) or gap > GAP_SPLIT or len(cur) >= MAX_WORDS or span > MAX_SECS
                    or (pw.endswith(",") and len(cur) >= 6)):
                out.append(cur)
                cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [{"s": round(p[0]["s"], 2), "e": round(p[-1]["e"], 2), "src": " ".join(x["w"].strip() for x in p)}
            for p in out]


def _key(p):
    return f"{p['start']:.2f}-{p['end']:.2f}"


def prepare(job: Path, to: str = "pt") -> dict:
    meta = read_json(job / "job.json") or {}
    chk = read_json(job / "moments.checked.json")
    if not chk:
        raise SystemExit("Run `check` first: moments.checked.json is missing")
    words = read_json(job / "transcript" / "words.json", [])
    src_lang = meta.get("language", "en")
    todo = {"from": src_lang, "to": to, "clips": {}}
    md = [f"# Tradução das legendas: {meta.get('title', '')}",
          f"De {LANG_NAMES.get(src_lang, src_lang)} para {LANG_NAMES.get(to, to)}.", "",
          "Escreva `translation.json` com o mesmo formato de `translation.todo.json`: em cada clipe, "
          "`lines` tem exatamente uma linha traduzida por frase, na mesma ordem (pode ser \"\" para "
          "barulho / frase sem sentido). Tradução natural e curta, como legenda de canal de cortes: "
          "adapte gíria e palavrão, não traduza palavra por palavra. Mantenha nomes próprios.", ""]
    for p in sorted(chk["picks"], key=lambda q: q["order"]):
        ph = phrases(clip_words(words, p["start"], p["end"]))
        todo["clips"][str(p["order"])] = {"key": _key(p), "src": [x["src"] for x in ph], "lines": []}
        md += [f"## Clipe {p['order']}: {fmt_ts(p['start'])} - {fmt_ts(p['end'])} ({len(ph)} frases)", ""]
        md += [f"{i}. [{x['s'] - p['start']:.1f}-{x['e'] - p['start']:.1f} s] {x['src']}" for i, x in enumerate(ph, 1)]
        md.append("")
    write_json(job / "translation.todo.json", todo)
    write_text(job / "translate.md", "\n".join(md) + "\n")
    return todo


def load(job: Path, picks) -> dict:
    """translation.json validated against the current checked picks -> {order: [lines]}.
    Raises SystemExit if it is out of date (cuts changed after translating)."""
    tr = read_json(job / "translation.json")
    if not tr:
        return {}
    words = read_json(job / "transcript" / "words.json", [])
    clips = tr.get("clips") or {}
    out, errs = {}, []
    for p in picks:
        c = clips.get(str(p["order"]))
        if c is None:
            errs.append(f"clipe {p['order']}: não está em translation.json")
            continue
        n = len(phrases(clip_words(words, p["start"], p["end"])))
        lines = c.get("lines") or []
        if c.get("key") and c["key"] != _key(p):
            errs.append(f"clipe {p['order']}: o corte mudou depois da tradução (rode translate de novo)")
        elif len(lines) != n:
            errs.append(f"clipe {p['order']}: {len(lines)} linhas traduzidas para {n} frases")
        else:
            out[p["order"]] = [str(x) for x in lines]
    if errs:
        raise SystemExit("translation.json inválido: " + "; ".join(errs))
    return {"to": tr.get("to", "pt"), "lines": out}


def translated_words(ws, lines):
    """Synthetic word list in the target language with times: each phrase's translated words are
    spread over the original phrase's span, weighted by length (longer words stay lit longer)."""
    out = []
    phs = phrases(ws)
    for k, (ph, line) in enumerate(zip(phs, lines)):
        toks = [t for t in re.split(r"\s+", line.strip()) if t]
        if not toks:
            continue
        s, e = ph["s"], ph["e"]
        span = max(e - s, 0.25 * len(toks))   # a short "Wow." translated to more words needs room
        if k + 1 < len(phs):
            span = min(span, max(e - s, phs[k + 1]["s"] - 0.05 - s))
        span = max(span, 0.1)
        weights = [len(re.sub(r"\W", "", t)) + 2 for t in toks]
        tot = float(sum(weights))
        t = s
        for tok, wgt in zip(toks, weights):
            d = span * wgt / tot
            out.append({"s": round(t, 3), "e": round(t + d - 0.02, 3), "w": tok})
            t += d
    return out
