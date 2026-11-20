"""Contratos e catálogo de plataformas para o fluxo de publicação."""
from __future__ import annotations

from .integrations.base import Account, Connector, Platform, PublishRequest

PLATFORMS = [
    Platform("youtube", "YouTube Shorts", "Publique clipes verticais no seu canal.", "YouTube Data API v3"),
    Platform("instagram", "Instagram Reels", "Distribua clipes no Instagram.", "Instagram Graph API"),
    Platform("tiktok", "TikTok", "Compartilhe os melhores momentos.", "TikTok Content Posting API"),
    Platform("facebook", "Facebook Reels", "Alcance novas audiências.", "Facebook Graph API (Reels)"),
]

UNAVAILABLE, DISCONNECTED, CONNECTED, EXPIRED = "unavailable", "disconnected", "connected", "expired"


def connector_for(platform: str) -> Connector | None:
    """A conta YouTube é gerenciada pelo AppState para compartilhar OAuth e histórico entre páginas."""
    return None


def status_of(platform: str) -> str:
    return UNAVAILABLE


def connected_accounts() -> list[Account]:
    return []


def publish_queue() -> list[PublishRequest]:
    return []
