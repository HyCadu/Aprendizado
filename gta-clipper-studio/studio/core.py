"""Lógica pura (sem Qt): validação do link, montagem do comando e leitura dos eventos do Claude Code.

O app não recria o processamento: ele roda o mesmo comando que cortes-youtube/rodar_automatico.ps1 e
clipper-gta-br/rodar_automatico.ps1 já usam (`claude -p "/skill LINK ..."`), só que pedindo a saída em
stream-json para mostrar os passos ao vivo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import os
import sys
import time


def _find_repo() -> Path:
    """Raiz do projeto (pasta com .claude/skills/cortes-youtube). Funciona rodando pelo .py ou pelo .exe."""
    starts = []
    if os.environ.get("GTA_CLIPPER_REPO"):
        starts.append(Path(os.environ["GTA_CLIPPER_REPO"]))
    if getattr(sys, "frozen", False):
        starts.append(Path(sys.executable).resolve().parent)
    starts.append(Path(__file__).resolve().parent)
    for s in starts:
        for d in (s, *s.parents):
            if (d / ".claude" / "skills" / "cortes-youtube" / "SKILL.md").is_file():
                return d
    return Path.home() / "Documents" / "Aprendizado"


REPO = _find_repo()
SKILLS = REPO / ".claude" / "skills"
HOME = Path.home()
DEFAULT_YT_OUT = HOME / "CortesYouTube"
DEFAULT_TW_OUT = HOME / "StreamClipper"
AI_STREAM_CLIPPER = HOME / ".claude" / "skills" / "ai-stream-clipper"
CLIPPER_CONFIG = HOME / ".ai-stream-clipper" / "config.json"

WHISPER_LOCK = HOME / ".ai-stream-clipper" / "whisper.lock"  # trava "uma transcrição por vez" das duas skills


def pid_alive(pid: int) -> bool:
    """O processo ainda existe? Só consulta, nunca mexe no processo."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.GetLastError() == 5  # acesso negado = existe, mas é de outro usuário
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def clear_stale_whisper_lock(lock: Path = WHISPER_LOCK) -> int | None:
    """Apaga a trava da GPU deixada por uma transcrição que morreu (ex.: corte cancelado no meio, o que mata o
    python à força e ele não solta a trava). Sem isso o próximo prepare fica "waiting for the GPU" por até 3 h.
    Só apaga se o PID gravado nela não existe mais. Retorna o PID removido."""
    try:
        raw = lock.read_text(encoding="ascii", errors="ignore").strip()
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return None
    pid = int(raw) if raw.isdigit() else 0
    if pid == 0 and age < 60:
        return None  # acabou de ser criada e o PID ainda está sendo gravado
    if pid and pid_alive(pid):
        return None
    try:
        lock.unlink()
    except OSError:
        return None
    return pid


YOUTUBE, TWITCH = "youtube", "twitch"
MAX_CLIPS = {YOUTUBE: 10, TWITCH: 10}  # limites das próprias skills (--top 1..10) / rodar_automatico.ps1

# Exatamente as permissões dos rodar_automatico.ps1: python dos scripts e leitura/escrita de arquivos.
# Nada de rede/publicação além do que os scripts da skill fazem.
ALLOWED_TOOLS = ["Bash(python:*)", "PowerShell(python:*)", "Read", "Write", "Glob"]
# As skills mandam prefixar `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`; com o prefixo, `Bash(python:*)` não casa e o
# comando cai em "requires approval". Libera esse mesmo formato (continua sendo só python).
ALLOWED_TOOLS_EXTRA = ["Bash(PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python:*)"]
# O runner já põe PYTHONUTF8, PYTHONIOENCODING e o Python certo no PATH do processo.
APPEND_PROMPT = (
    "Ambiente do GTA CLIPPER STUDIO (sem ninguém para aprovar comandos): PYTHONUTF8=1, PYTHONIOENCODING=utf-8 e o "
    "Python 3.12 no PATH já estão definidos, e a pasta atual já é a raiz do repositório. Rode todo script como um "
    "comando simples que começa com `python -I ...` (ferramenta Bash), sem prefixo de variáveis, sem `export`, "
    "sem `cd`, sem `&&`/`;`, sem caminho completo do python e sem `$env:`. Qualquer outro formato é bloqueado. "
    "O app só marca o corte como concluído quando esta sessão termina: não deixe nada vigiando em segundo plano "
    "(nada de Monitor, `tail -f` ou laço de espera). Para prepare e render, rode o comando e espere ele acabar "
    "(em background, aguarde a notificação de fim). Depois da resposta final, não espere mais nada. "
    "Nunca publique nada.")
# Monitor (tail -f no log) nunca termina sozinho: o claude -p ficava vivo depois dos clipes prontos e o app
# continuava em "processando" até o monitor expirar.
DISALLOWED_TOOLS = ["Monitor"]

_YT_RE = re.compile(
    r"^https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)[\w-]{6,}[\w\-=&%.]*"
    r"|youtu\.be/[\w-]{6,}[\w\-=&?%.]*)$", re.I)
_TW_RE = re.compile(r"^https?://(?:www\.|m\.)?twitch\.tv/videos/\d+[\w\-=&?%.]*$", re.I)


def detect_platform(url: str) -> str | None:
    url = (url or "").strip()
    if _YT_RE.match(url):
        return YOUTUBE
    if _TW_RE.match(url):
        return TWITCH
    return None


def validate_link(url: str, platform: str) -> tuple[bool, str]:
    """Só aceita link de vídeo do YouTube ou VOD da Twitch, sem espaços: o texto vira parte do prompt,
    então nada além de uma URL limpa pode passar."""
    url = (url or "").strip()
    if not url:
        return False, "Cole o link do vídeo."
    if any(c.isspace() for c in url) or any(c in url for c in "\"'`<>|;$"):
        return False, "O link tem caracteres inválidos."
    found = detect_platform(url)
    if found is None:
        return False, ("Link não reconhecido. Use um vídeo do YouTube (youtube.com/watch?v=… ou youtu.be/…) "
                       "ou um VOD da Twitch (twitch.tv/videos/…).")
    if platform == YOUTUBE and found == TWITCH:
        return False, "Este link é da Twitch. Selecione Twitch (lives)."
    # Live que virou vídeo no YouTube pode ir para o fluxo de lives (clipar-gta-br aceita YouTube).
    return True, ""


def _safe_dir(p: str | Path) -> str:
    s = str(p)
    if any(c in s for c in "\"\r\n`"):
        raise ValueError("pasta com caracteres inválidos")
    return s


# Idioma falado no vídeo (só no modo YouTube; o fluxo de lives é sempre pt-BR).
AUTO_LANG = "auto"
LANGS = {AUTO_LANG: "Detectar", "pt": "Português", "en": "Inglês", "es": "Espanhol"}
LANG_NAMES = {"pt": "português", "en": "inglês", "es": "espanhol", "ru": "russo", "fr": "francês",
              "de": "alemão", "it": "italiano", "ja": "japonês", "ko": "coreano"}


def lang_name(code: str) -> str:
    return LANG_NAMES.get((code or "").lower(), code or "?")


NO_ZOOM_HINT = " (sem zoom: renderize com --no-zoom)"
NO_COVER_HINT = " (sem capa: renderize com --no-cover)"
ORIGINAL_HINT ="; mantenha a legenda no idioma original: pule o translate e renderize com --original-captions"


def live_language_hint(lang: str, original_captions: bool = False) -> str:
    """Fluxo de lives (clipar-gta-br): a skill manda --lang pt; vale só para streamer brasileiro.
    Live gringa: transcrição no idioma falado e legenda traduzida para pt-BR (passo 4b da ai-stream-clipper)."""
    lang = lang if lang in LANGS else AUTO_LANG
    if lang == "pt":
        return ""
    if lang == AUTO_LANG:
        hint = (" (idioma não informado: o --lang pt da skill vale só se o título/canal deixar claro que a live é "
                "brasileira; senão use --lang auto no prepare")
    else:
        hint = f" (a live é falada em {lang_name(lang)}: use --lang {lang} no prepare em vez de --lang pt"
    if original_captions:
        hint += ("; se não for em português" if lang == AUTO_LANG else "") + ORIGINAL_HINT
    else:
        hint += "; live gringa ganha legenda traduzida para pt-BR (passo 4b)"
    return hint + ")"


def language_hint(lang: str, original_captions: bool) -> str:
    """Instrução extra do prompt sobre o idioma. Só códigos conhecidos entram no prompt."""
    lang = lang if lang in LANGS else AUTO_LANG
    if lang == AUTO_LANG:
        hint = (" (idioma não informado: só use --lang pt no prepare se o título/canal deixar claro que o vídeo é "
                "brasileiro; na dúvida use --lang auto e siga pelo language do job.json")
    else:
        hint = f" (o vídeo é falado em {lang_name(lang)}: use --lang {lang} no prepare"
    if original_captions and lang != "pt":
        hint += ("; se não for em português" if lang == AUTO_LANG else "") + ORIGINAL_HINT
    return hint + ")"


def build_command(claude: str, url: str, platform: str, clips: int, out_dir: Path | None,
                  lang: str = AUTO_LANG, original_captions: bool = False,
                  zoom: bool = True, cover: bool = True) -> tuple[list[str], str]:
    """Mesmo prompt dos rodar_automatico.ps1 (+ dica de idioma). Retorna (argv, prompt)."""
    clips = max(1, min(int(clips), MAX_CLIPS[platform]))
    if platform == YOUTUBE:
        # legenda em pt-BR (a skill traduz se o vídeo for gringo), a não ser que peça a legenda original
        legenda = "" if original_captions and lang != "pt" else " --legenda pt"
        prompt = f"/cortes-youtube {url} --top {clips}{legenda}" + language_hint(lang, original_captions)
        default_out, extra = DEFAULT_YT_OUT, []
    else:
        prompt = f"/clipar-gta-br {url} (só {clips} cortes por live)" + live_language_hint(lang, original_captions)
        default_out, extra = DEFAULT_TW_OUT, ["--add-dir", str(AI_STREAM_CLIPPER)]
    if not zoom:   # o zoom na narração forte é o padrão do render; desligado, a skill recebe --no-zoom
        prompt += NO_ZOOM_HINT
    if not cover:  # a capa (<clipe>_capa.jpg) é padrão do render; desligada, a skill recebe --no-cover
        prompt += NO_COVER_HINT
    out = Path(out_dir) if out_dir else default_out
    if out.resolve() != default_out.resolve():
        prompt += f' (salve o job com --out "{_safe_dir(out)}" no prepare)'
    argv = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--allowedTools", *ALLOWED_TOOLS, *ALLOWED_TOOLS_EXTRA,
            "--disallowedTools", *DISALLOWED_TOOLS,
            "--append-system-prompt", APPEND_PROMPT, "--add-dir", str(out), *extra]
    return argv, prompt


# ---------------------------------------------------------------- etapas
@dataclass(frozen=True)
class Step:
    key: str
    label: str
    start: float  # % da barra quando a etapa começa
    end: float    # % máximo enquanto ela roda


STEPS = [
    Step("start", "Iniciando o Claude Code", 0, 4),
    Step("verify", "Verificando o vídeo", 4, 10),
    Step("prepare", "Download e transcrição", 10, 45),
    Step("pick", "Escolhendo os melhores momentos", 45, 66),
    Step("check", "Conferindo os cortes", 66, 72),
    Step("translate", "Traduzindo a legenda", 72, 78),
    Step("render", "Renderizando os clipes", 78, 96),
    Step("finish", "Finalizando", 96, 100),
]
STEP_INDEX = {s.key: i for i, s in enumerate(STEPS)}


def step_for_command(cmd: str) -> str | None:
    c = " " + (cmd or "").replace("\\", "/") + " "
    if "--marcar" in c:
        return "finish"
    if "novos_videos.py" in c or "novas_lives.py" in c or "clipper.py setup" in c:
        return "verify"
    for key in ("prepare", "check", "translate", "render"):
        if re.search(rf"clipper\.py\"?\s+{key}\b", c):
            return key
    return None


def step_for_file(tool: str, path: str) -> str | None:
    p = (path or "").replace("\\", "/").lower()
    if tool == "Write" and p.endswith("moments.json"):
        return "pick"
    if tool == "Write" and p.endswith("translation.json"):
        return "translate"
    if tool == "Read" and ("/chunks/" in p or p.endswith("index.md")):
        return "pick"
    if tool == "Read" and p.endswith("sheet.jpg"):
        return "render"
    return None


# ---------------------------------------------------------------- segredos
_SECRET_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "sk-ant-••••••"),
    (re.compile(r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|token|password|senha|secret|cookie)"
                r"(\s*[:=]\s*)[\"']?[^\s\"',;]{6,}"), r"\1\2••••••"),
    (re.compile(r"(?i)\b(authorization:\s*(?:bearer\s+|basic\s+)?|bearer\s+)[^\s\"',;]{6,}"), r"\1••••••"),
]


def redact(text: str) -> str:
    """Esconde qualquer coisa com cara de credencial antes de mostrar ou gravar no log."""
    for rx, repl in _SECRET_PATTERNS:
        text = rx.sub(repl, text)
    return text


# ---------------------------------------------------------------- eventos
@dataclass
class Event:
    kind: str           # info | cmd | output | claude | error | result | raw
    text: str
    step: str | None = None
    data: dict = field(default_factory=dict)


MP4_RE = re.compile(r"[A-Za-z]:[\\/][^\n\r*?\"<>|]*?\.mp4", re.I)
# Linhas do clipper.py que dizem o idioma do vídeo: transcrição nova ou job já existente.
LANG_RE = re.compile(r"whisper: language = ([a-z]{2,3})\b|\|\s*language ([a-z]{2,3})\s*\|", re.I)
TRANSLATED_RE = re.compile(r"captions: translated to ([a-z]{2,3})\b", re.I)


def language_events(text: str) -> list[Event]:
    """Detecta na saída dos scripts o idioma do vídeo e se a legenda foi traduzida."""
    evs = []
    m = LANG_RE.search(text or "")
    if m:
        code = (m.group(1) or m.group(2)).lower()
        evs.append(Event("lang", code, None, {"lang": code}))
    m = TRANSLATED_RE.search(text or "")
    if m:
        evs.append(Event("lang", m.group(1).lower(), None, {"translated": m.group(1).lower()}))
    return evs


def _short(text: str, max_lines: int = 14, max_chars: int = 2400) -> str:
    text = text.strip("\n")
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:4] + [f"… ({len(lines) - max_lines + 4} linhas omitidas) …"] + lines[-(max_lines - 5):]
    out = "\n".join(lines)
    return out if len(out) <= max_chars else out[:600] + "\n…\n" + out[-(max_chars - 700):]


def _tool_result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif isinstance(c, dict) and c.get("type") == "image":
                parts.append("[imagem]")
        return "\n".join(parts)
    return ""


def describe_tool(name: str, inp: dict) -> tuple[str, str | None]:
    """Texto amigável para uma chamada de ferramenta + etapa detectada."""
    if name in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        return f"$ {cmd}", step_for_command(cmd)
    path = str(inp.get("file_path") or inp.get("path") or inp.get("pattern") or "")
    labels = {"Read": "Lendo", "Write": "Escrevendo", "Glob": "Procurando", "Edit": "Editando",
              "Skill": "Carregando skill"}
    if name == "Skill":
        return f"Carregando skill {inp.get('skill', '')}", "verify"
    return f"{labels.get(name, name)} {path}".strip(), step_for_file(name, path)


class StreamParser:
    """Converte as linhas de `claude -p --output-format stream-json --verbose` em Events."""

    def __init__(self):
        self.tools: dict[str, str] = {}
        self.result: dict | None = None

    def feed(self, line: str) -> list[Event]:
        line = line.strip()
        if not line:
            return []
        try:
            msg = json.loads(line)
        except ValueError:
            return [Event("raw", redact(line))]
        if not isinstance(msg, dict):
            return []
        t = msg.get("type")
        if t == "system" and msg.get("subtype") == "init":
            model = msg.get("model", "")
            return [Event("info", f"Claude Code iniciado ({model}).", "start")]
        if t == "assistant":
            evs = []
            for c in (msg.get("message") or {}).get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and c.get("text", "").strip():
                    evs.append(Event("claude", redact(c["text"].strip())))
                elif c.get("type") == "tool_use":
                    name = c.get("name", "")
                    self.tools[c.get("id", "")] = name
                    text, step = describe_tool(name, c.get("input") or {})
                    evs.append(Event("cmd", redact(text), step, {"tool": name}))
            return evs
        if t == "user":
            evs = []
            content = (msg.get("message") or {}).get("content") or []
            if not isinstance(content, list):
                return []
            for c in content:
                if not isinstance(c, dict) or c.get("type") != "tool_result":
                    continue
                tool = self.tools.get(c.get("tool_use_id", ""), "")
                text = _tool_result_text(c.get("content"))
                if tool in ("Read", "Glob") and not c.get("is_error"):
                    continue  # conteúdo de arquivo/transcrição: não poluir o log
                if not text.strip():
                    continue
                kind = "error" if c.get("is_error") else "output"
                evs.append(Event(kind, redact(_short(text)), None, {"tool": tool}))
                if tool in ("Bash", "PowerShell") and not c.get("is_error"):
                    evs.extend(language_events(text))
            return evs
        if t == "result":
            self.result = msg
            text = str(msg.get("result") or "")
            ok = not msg.get("is_error") and msg.get("subtype") == "success"
            # Sem etapa: com comando em background o Claude encerra o turno e continua no mesmo processo
            # quando ele termina. O fim de verdade é o processo sair.
            return [Event("result", redact(text), None,
                          {"ok": ok, "duration_ms": msg.get("duration_ms"),
                           "mp4": sorted(set(MP4_RE.findall(text)))})]
        return []
