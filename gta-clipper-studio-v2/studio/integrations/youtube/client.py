"""Cliente da YouTube Data API v3, com credenciais oficiais e erros localizados."""
from __future__ import annotations

from ..models import ChannelNotFound, IntegrationError, friendly_api_error
from .auth import YouTubeAuth


class YouTubeClient:
    def __init__(self, auth: YouTubeAuth | None = None, service_builder=None):
        self.auth = auth or YouTubeAuth()
        self._service_builder = service_builder

    def service(self):
        credentials = self.auth.credentials()
        if self._service_builder is None:
            try:
                from googleapiclient.discovery import build
            except ImportError:
                raise IntegrationError("As bibliotecas oficiais do Google não estão instaladas. Reinstale o GTA Clipper Studio.",
                                       "unavailable") from None
            builder = build
        else:
            builder = self._service_builder
        try:
            return builder("youtube", "v3", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            raise friendly_api_error(exc) from None

    def get_channel(self, api=None) -> dict:
        api = api or self.service()
        try:
            result = api.channels().list(part="snippet,statistics", mine=True, maxResults=1).execute()
        except Exception as exc:
            raise friendly_api_error(exc) from None
        channels = result.get("items") or []
        if not channels:
            raise ChannelNotFound()
        item = channels[0]
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        thumbnails = snippet.get("thumbnails") or {}
        thumbnail = (thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {}).get("url")
        return {
            "id": item.get("id", ""),
            "title": snippet.get("title", "Canal do YouTube"),
            "description": snippet.get("description", ""),
            "custom_url": snippet.get("customUrl", ""),
            "thumbnail": thumbnail or "",
            "subscribers": stats.get("subscriberCount"),
            "videos": stats.get("videoCount"),
            "views": stats.get("viewCount"),
            "url": f"https://www.youtube.com/channel/{item.get('id', '')}",
        }

    def list_videos(self, ids: list[str]) -> dict:
        if not ids:
            return {}
        api = self.service()
        try:
            result = api.videos().list(part="status,processingDetails,snippet", id=",".join(ids[:50])).execute()
        except Exception as exc:
            raise friendly_api_error(exc) from None
        return {item.get("id"): item for item in result.get("items", []) if item.get("id")}
