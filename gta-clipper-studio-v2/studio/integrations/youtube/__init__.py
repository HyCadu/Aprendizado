"""Integração oficial com a YouTube Data API v3."""

from .auth import YouTubeAuth
from .client import YouTubeClient

__all__ = ["YouTubeAuth", "YouTubeClient"]
