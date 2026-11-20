"""Valida, envia e reconcilia publicações pela YouTube Data API oficial."""
from __future__ import annotations

import hashlib
import mimetypes
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from ..integrations.base import PublishRequest
from ..integrations.models import (IntegrationError, UploadCancelled, UploadOutcomeUnknown,
                                   friendly_api_error)
from ..integrations.youtube.validators import validate_publish_request, video_resource
from .publication_storage import PublicationStorage, utc_now

TRANSIENT_HTTP_CODES = {500, 502, 503, 504}


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _publish_date(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.isoformat(timespec="seconds")


def remote_publication_status(item: dict, now: datetime | None = None) -> str:
    status = item.get("status") or {}
    processing = item.get("processingDetails") or {}
    upload_status = status.get("uploadStatus", "")
    process_status = processing.get("processingStatus", "")
    if upload_status in ("failed", "rejected") or process_status == "failed":
        return "failed"
    if status.get("publishAt"):
        return "scheduled"
    if process_status not in ("succeeded", "terminated") and upload_status != "processed":
        return "processing"
    return {"public": "published", "unlisted": "unlisted", "private": "private"}.get(
        status.get("privacyStatus"), "unknown")


class PublicationService:
    def __init__(self, youtube_client, storage: PublicationStorage | None = None, media_upload_factory=None,
                 sleep=time.sleep):
        self.youtube = youtube_client
        self.storage = storage or PublicationStorage()
        self._media_upload_factory = media_upload_factory
        self._sleep = sleep

    def _media_factory(self):
        if self._media_upload_factory is None:
            try:
                from googleapiclient.http import MediaFileUpload
            except ImportError:
                raise IntegrationError("As bibliotecas oficiais do Google não estão instaladas. Reinstale o GTA Clipper Studio.",
                                       "unavailable") from None
            self._media_upload_factory = MediaFileUpload
        return self._media_upload_factory

    @staticmethod
    def _report(progress, uploaded: int, total: int, stage: str):
        if progress:
            try:
                progress(max(0, min(uploaded, total)), total, stage)
            except Exception:
                pass

    @staticmethod
    def _http_code(exc: Exception):
        return getattr(getattr(exc, "resp", None), "status", None)

    def publish(self, req: PublishRequest, progress=None, cancelled=None) -> dict:
        file, scheduled = validate_publish_request(req)
        body = video_resource(req, scheduled)
        cancelled = cancelled or (lambda: False)
        if cancelled():
            raise UploadCancelled()

        # Confirma o canal autenticado no momento da publicação e usa o mesmo cliente no upload.
        api = self.youtube.service()
        channel = self.youtube.get_channel(api=api)
        if req.channel_id and req.channel_id != channel["id"]:
            raise IntegrationError("O canal conectado mudou. Atualize a página Integrações antes de enviar.", "error")
        digest = sha256_file(file)
        record = self.storage.create(
            clip_id=req.clip_id or str(file.parent), file_hash=digest, platform="youtube",
            channel_id=channel["id"], channel_name=channel["title"], title=req.title.strip(),
            description=req.description, publish_at=_publish_date(scheduled),
            visibility="private" if scheduled else req.privacy_status, status="queued", file_path=str(file))
        record_id = record["id"]
        total = file.stat().st_size
        self._report(progress, 0, total, "Preparando envio")
        upload_started = False
        try:
            mime_type = mimetypes.guess_type(str(file))[0] or "video/mp4"
            media = self._media_factory()(str(file), mimetype=mime_type, chunksize=8 * 1024 * 1024, resumable=True)
            self.storage.update(record_id, status="uploading", error=None)
            insert = api.videos().insert(part="snippet,status", body=body, media_body=media)
            upload_started = True
            response = None
            retries = 0
            uploaded = 0
            while response is None:
                if cancelled():
                    self.storage.update(record_id, status="cancelled", error="Cancelado pelo usuário.")
                    raise UploadCancelled()
                try:
                    status, response = insert.next_chunk(num_retries=0)
                    retries = 0
                    if status is not None:
                        uploaded = int(status.resumable_progress)
                        self._report(progress, uploaded, total, "Enviando vídeo")
                except Exception as exc:
                    code = self._http_code(exc)
                    if code in TRANSIENT_HTTP_CODES and retries < 3:
                        delay = 2 ** retries
                        retries += 1
                        self._report(progress, uploaded, total, f"Falha temporária; nova tentativa em {delay}s")
                        for _ in range(delay * 10):
                            if cancelled():
                                self.storage.update(record_id, status="unknown",
                                                    error="Cancelamento durante resposta temporária; confirme no YouTube Studio.")
                                raise UploadOutcomeUnknown()
                            self._sleep(0.1)
                        continue
                    if code in TRANSIENT_HTTP_CODES or code is None:
                        self.storage.update(record_id, status="unknown",
                                            error="O resultado da sessão de upload não pôde ser confirmado.")
                        raise UploadOutcomeUnknown() from None
                    raise friendly_api_error(exc) from None

            video_id = response.get("id") if isinstance(response, dict) else None
            if not video_id:
                self.storage.update(record_id, status="unknown", error="A API concluiu o envio sem retornar o ID do vídeo.")
                raise UploadOutcomeUnknown()
            url = f"https://www.youtube.com/watch?v={video_id}"
            self.storage.update(record_id, video_id=video_id, url=url, uploaded_at=utc_now(), status="processing",
                                error=None)
            self._report(progress, total, total, "Arquivo enviado; aguardando o processamento do YouTube")
            try:
                remote = self.youtube.list_videos([video_id]).get(video_id)
                if remote:
                    remote_status = remote_publication_status(remote)
                    self.storage.update(record_id, status=remote_status,
                                        error="O YouTube informou falha no processamento." if remote_status == "failed" else None)
            except IntegrationError:
                # O envio e seu ID já foram confirmados. A reconciliação fica para depois.
                pass
            return self.storage.get(record_id)
        except UploadCancelled:
            raise
        except UploadOutcomeUnknown:
            raise
        except IntegrationError as exc:
            if self.storage.get(record_id).get("status") not in ("unknown", "cancelled"):
                self.storage.update(record_id, status="failed", error=str(exc))
            raise
        except Exception as exc:
            if upload_started:
                self.storage.update(record_id, status="unknown",
                                    error="A conexão foi interrompida e o resultado do envio é desconhecido.")
                raise UploadOutcomeUnknown() from None
            mapped = IntegrationError("Não foi possível iniciar o envio. Verifique o arquivo e a conexão com o YouTube.",
                                      "error")
            self.storage.update(record_id, status="failed", error=str(mapped))
            raise mapped from None

    def reconcile(self) -> list[dict]:
        records = self.storage.pending_reconciliation()
        video_ids = list(dict.fromkeys(row["video_id"] for row in records if row.get("video_id")))
        if not video_ids:
            return records
        items = self.youtube.list_videos(video_ids)
        for row in records:
            item = items.get(row["video_id"])
            if item:
                status = remote_publication_status(item)
                self.storage.update(row["id"], status=status,
                                    error="O YouTube informou falha no processamento." if status == "failed" else None)
        return self.storage.list_recent()
