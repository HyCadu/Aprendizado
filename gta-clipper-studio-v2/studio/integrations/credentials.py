"""Armazenamento de segredos no cofre do sistema; nunca grava tokens em JSON."""
from __future__ import annotations

import json
import os

from .models import CredentialStoreUnavailable

SERVICE = "GTAClipperStudio.YouTube"
CLIENT_KEY = "oauth_client"
TOKEN_KEY = "oauth_token"


class CredentialVault:
    def __init__(self, keyring_module=None):
        try:
            if keyring_module is None:
                import keyring as keyring_module  # type: ignore[no-redef]
            self._keyring = keyring_module
            backend = keyring_module.get_keyring()
            # No Windows, não aceite um backend alternativo em arquivo sem criptografia.
            if os.name == "nt" and not type(backend).__module__.startswith("keyring.backends.Windows"):
                raise CredentialStoreUnavailable()
        except CredentialStoreUnavailable:
            raise
        except Exception:
            raise CredentialStoreUnavailable() from None

    def get(self, name: str) -> str | None:
        try:
            return self._keyring.get_password(SERVICE, name)
        except Exception:
            raise CredentialStoreUnavailable() from None

    def set(self, name: str, value: str) -> None:
        try:
            self._keyring.set_password(SERVICE, name, value)
        except Exception:
            raise CredentialStoreUnavailable() from None

    def delete(self, name: str) -> None:
        try:
            self._keyring.delete_password(SERVICE, name)
        except Exception as exc:
            if type(exc).__name__ != "PasswordDeleteError":
                raise CredentialStoreUnavailable() from None

    def get_json(self, name: str):
        value = self.get(name)
        if not value:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            raise CredentialStoreUnavailable() from None

    def set_json(self, name: str, value) -> None:
        self.set(name, json.dumps(value, ensure_ascii=False, separators=(",", ":")))
