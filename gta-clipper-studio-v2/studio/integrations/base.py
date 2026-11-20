"""Contratos comuns para integrações com plataformas de publicação."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Platform:
    key: str
    name: str
    description: str
    official_api: str


@dataclass
class Account:
    platform: str
    display_name: str
    channel: str = ""
    scopes: list[str] = field(default_factory=list)
    status: str = "connected"


@dataclass
class PublishRequest:
    clip_path: str
    platform: str
    title: str
    description: str
    hashtags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    category_id: str = "20"
    language: str = "pt"
    made_for_kids: bool | None = None
    contains_synthetic_media: bool = False
    privacy_status: str = "private"
    scheduled_for: str | None = None
    rights_confirmed: bool = False
    clip_id: str = ""
    channel_id: str = ""


class Connector(Protocol):
    platform: str

    def status(self) -> str: ...
    def connect(self) -> Account: ...
    def disconnect(self) -> None: ...
    def publish(self, req: PublishRequest) -> str: ...
