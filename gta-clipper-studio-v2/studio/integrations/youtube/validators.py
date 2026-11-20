"""Validação e montagem dos metadados aceitos pela YouTube Data API v3."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..base import PublishRequest
from ..models import IntegrationError

MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAGS_LENGTH = 500
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".3gp", ".m4v"}


def validate_video_file(path: str | Path) -> Path:
    file = Path(path).expanduser()
    if file.suffix.lower() not in VIDEO_SUFFIXES:
        raise IntegrationError("O formato do vídeo não é aceito. Escolha um arquivo MP4, MOV, AVI, WMV ou WebM.",
                               "invalid_video")
    try:
        if not file.is_file() or file.stat().st_size <= 0:
            raise OSError()
        with file.open("rb") as stream:
            stream.read(1)
    except OSError:
        raise IntegrationError("O arquivo de vídeo não existe ou não pode ser lido.", "invalid_video") from None
    return file


def parse_post_metadata(path: str | Path, defaults: dict) -> dict:
    """Lê post.md sem alterar o arquivo e tolera os templates usados pelas skills."""
    result = {"title": defaults.get("title", ""), "description": defaults.get("description", ""),
              "hashtags": list(defaults.get("hashtags") or [])}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
    sections = re.split(r"(?m)^#{1,3}\s+", text)
    selected = next((part for part in sections if re.search(r"youtube|shorts|t[ií]tulo|descri[cç][aã]o", part, re.I)), text)
    title_match = re.search(r"(?im)^\s*(?:t[ií]tulo\s*:\s*|title\s*:\s*|#\s+)(.+?)\s*$", selected)
    if title_match and title_match.group(1).strip():
        result["title"] = title_match.group(1).strip()[:MAX_TITLE]
    desc_match = re.search(r"(?is)(?:descri[cç][aã]o|description)\s*:\s*(.+?)(?=\n\s*(?:hashtags?|tags?|t[ií]tulo|title)\s*:|\Z)", selected)
    if desc_match:
        description = desc_match.group(1).strip()
        description = re.sub(r"\n\s*(?:#[\wÀ-ÿ]+[\s,]*)+$", "", description).strip()
        result["description"] = description
    found = re.findall(r"(?<!\w)#[\wÀ-ÿ]+", selected)
    if found:
        result["hashtags"] = list(dict.fromkeys(found))
    return result


def validate_publish_request(req: PublishRequest, now: datetime | None = None) -> tuple[Path, datetime | None]:
    if req.platform != "youtube":
        raise IntegrationError("Esta publicação não usa o conector do YouTube.", "invalid_metadata")
    file = validate_video_file(req.clip_path)
    title = (req.title or "").strip()
    description = req.description or ""
    if not title or len(title) > MAX_TITLE:
        raise IntegrationError("O título é obrigatório e deve ter no máximo 100 caracteres.", "invalid_metadata")
    if len(description) > MAX_DESCRIPTION:
        raise IntegrationError("A descrição deve ter no máximo 5.000 caracteres.", "invalid_metadata")
    if req.made_for_kids not in (True, False):
        raise IntegrationError("Escolha se o vídeo é ou não conteúdo para crianças.", "invalid_metadata")
    if not req.rights_confirmed:
        raise IntegrationError("Confirme que você tem autorização para publicar este conteúdo.", "invalid_metadata")
    if req.privacy_status not in ("public", "unlisted", "private"):
        raise IntegrationError("Selecione uma opção válida de visibilidade.", "invalid_metadata")
    tags = [str(tag).strip() for tag in req.tags if str(tag).strip()]
    tag_chars = sum(len(tag) for tag in tags) + max(0, len(tags) - 1)
    if tag_chars > MAX_TAGS_LENGTH:
        raise IntegrationError("As tags ultrapassam o limite permitido pelo YouTube.", "invalid_metadata")
    if not str(req.category_id).isdigit():
        raise IntegrationError("Selecione uma categoria válida para o vídeo.", "invalid_metadata")
    if req.language and not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", req.language):
        raise IntegrationError("Informe um código de idioma válido, como pt ou en.", "invalid_metadata")
    scheduled = None
    if req.scheduled_for:
        try:
            scheduled = datetime.fromisoformat(req.scheduled_for.replace("Z", "+00:00"))
        except ValueError:
            raise IntegrationError("A data e o horário do agendamento são inválidos.", "invalid_metadata") from None
        if scheduled.tzinfo is None:
            raise IntegrationError("O horário do agendamento precisa incluir o fuso horário local.", "invalid_metadata")
        current = now or datetime.now(timezone.utc)
        if scheduled.astimezone(timezone.utc) <= current.astimezone(timezone.utc):
            raise IntegrationError("Escolha uma data e um horário futuros para o agendamento.", "invalid_metadata")
    return file, scheduled


def video_resource(req: PublishRequest, scheduled: datetime | None = None) -> dict:
    tags = [str(tag).strip() for tag in req.tags if str(tag).strip()]
    hashtags = [tag if tag.startswith("#") else f"#{tag}" for tag in req.hashtags if str(tag).strip()]
    description = (req.description or "").strip()
    if hashtags:
        description = "\n\n".join(x for x in (description, " ".join(hashtags)) if x)
    if len(description) > MAX_DESCRIPTION:
        raise IntegrationError("A descrição e as hashtags ultrapassam o limite de 5.000 caracteres.", "invalid_metadata")
    snippet = {"title": req.title.strip(), "description": description, "categoryId": str(req.category_id)}
    if tags:
        snippet["tags"] = tags
    if req.language:
        snippet["defaultLanguage"] = req.language
    status = {"privacyStatus": "private" if scheduled else req.privacy_status,
              "selfDeclaredMadeForKids": bool(req.made_for_kids),
              "containsSyntheticMedia": bool(req.contains_synthetic_media)}
    if scheduled:
        status["publishAt"] = scheduled.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"snippet": snippet, "status": status}


def probe_video(path: str | Path) -> dict:
    """Busca duração e dimensões em ffprobe sem bloquear a interface."""
    try:
        file = validate_video_file(path)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:format=duration", "-of", "json", str(file)],
            capture_output=True, text=True, timeout=8, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(result.stdout)
        stream = (data.get("streams") or [{}])[0]
        duration = float((data.get("format") or {}).get("duration", 0) or 0)
        width, height = int(stream.get("width", 0) or 0), int(stream.get("height", 0) or 0)
        if not width or not height:
            return {"duration": duration, "width": 0, "height": 0, "short": "unknown"}
        eligible = height >= width and 0 < duration <= 180
        return {"duration": duration, "width": width, "height": height, "short": "likely" if eligible else "no"}
    except Exception:
        return {"duration": None, "width": 0, "height": 0, "short": "unknown"}


def short_eligibility_text(info: dict) -> str:
    if info.get("short") == "likely":
        return "Formato vertical/quadrado e duração de até 3 minutos; o YouTube determina a classificação final."
    if info.get("short") == "no":
        return "Este arquivo não atende ao critério atual de proporção/duração para Shorts."
    return "Não foi possível verificar formato e duração. O YouTube determina a classificação final."
