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

YOUTUBE, TWITCH = "youtube", "twitch"
MAX_CLIPS = {YOUTUBE: 5, TWITCH: 3}  # limites das próprias skills / rodar_automatico.ps1

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
    "Nunca publique nada.")

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


LEGENDAS = {"pt": "Português (BR)", "en": "Inglês"}  # idiomas de legenda que as duas skills suportam


def build_command(claude: str, url: str, platform: str, clips: int, out_dir: Path | None,
                  legenda: str | None = None) -> tuple[list[str], str]:
    """Mesmo prompt dos rodar_automatico.ps1 (inclusive o -Legenda). Retorna (argv, prompt)."""
    clips = max(1, min(int(clips), MAX_CLIPS[platform]))
    if legenda is not None and legenda not in LEGENDAS:
        raise ValueError("idioma de legenda inválido")
    if platform == YOUTUBE:
        prompt = f"/cortes-youtube {url} --top {clips}"
        default_out, extra = DEFAULT_YT_OUT, []
    else:
        prompt = f"/clipar-gta-br {url} (só {clips} cortes por live)"
        default_out, extra = DEFAULT_TW_OUT, ["--add-dir", str(AI_STREAM_CLIPPER)]
    if legenda:
        prompt += f" --legenda {legenda}"
    out = Path(out_dir) if out_dir else default_out
    if out.resolve() != default_out.resolve():
        prompt += f' (salve o job com --out "{_safe_dir(out)}" no prepare)'
    argv = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose",
            "--allowedTools", *ALLOWED_TOOLS, *ALLOWED_TOOLS_EXTRA,
            "--append-system-prompt", APPEND_PROMPT, "--add-dir", str(out), *extra]
    return argv, prompt


# ---------------------------------------------------------------- etapas
@dataclass(frozen=True)
class Step:
    key: str
    label: str


# As etapas são detectadas pelos eventos reais do Claude (comandos e arquivos). Não há porcentagem:
# o pipeline não informa quanto falta dentro de cada etapa, então a interface não inventa.
STEPS = [
    Step("start", "Iniciando o Claude Code"),
    Step("verify", "Verificando o link"),
    Step("prepare", "Baixando e transcrevendo"),
    Step("pick", "Escolhendo os momentos"),
    Step("check", "Conferindo os cortes"),
    Step("translate", "Legenda no idioma escolhido"),
    Step("render", "Renderizando e checando a sincronia"),
    Step("finish", "Finalizando"),
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


AUTH_REQUIRED_MESSAGE = (
    "A autenticação do Claude Code falhou. Abra Configurações > Autenticação, clique em Autenticar "
    "e depois em Verificar novamente. Os dados do formulário foram mantidos."
)


def is_authentication_error(text: str) -> bool:
    normalized = (text or "").lower().replace("’", "'")
    return any(marker in normalized for marker in (
        "not logged in",
        "please run /login",
        "please run `claude auth login`",
        "not authenticated",
        "authentication required",
        "authentication_error",
        "authentication error",
        "failed to authenticate",
        "oauth token expired",
        "oauth token has expired",
        "invalid api key",
        "api key not found",
    ))


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
            return evs
        if t == "result":
            self.result = msg
            text = str(msg.get("result") or "")
            ok = not msg.get("is_error") and msg.get("subtype") == "success"
            return [Event("result", redact(text), "finish",
                          {"ok": ok, "duration_ms": msg.get("duration_ms"),
                           "mp4": sorted(set(MP4_RE.findall(text)))})]
        return []
