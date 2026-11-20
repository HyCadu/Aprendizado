"""OAuth 2.0 de aplicativo instalado, PKCE e callback temporário em loopback."""
from __future__ import annotations

import hmac
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from ..credentials import CLIENT_KEY, TOKEN_KEY, CredentialVault
from ..models import (AuthenticationExpired, AuthenticationRequired, CredentialStoreUnavailable,
                      CredentialsNotConfigured, IntegrationError, InvalidClientSecrets, LoginCancelled,
                      PermissionRequired)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"


class YouTubeAuth:
    def __init__(self, vault: CredentialVault | None = None, flow_class=None, credentials_class=None,
                 request_factory=None, browser_open=None):
        self.vault = vault or CredentialVault()
        self._flow_class = flow_class
        self._credentials_class = credentials_class
        self._request_factory = request_factory
        self._browser_open = browser_open or webbrowser.open

    @staticmethod
    def validate_client_config(data: dict) -> dict:
        installed = data.get("installed") if isinstance(data, dict) else None
        required = ("client_id", "client_secret", "auth_uri", "token_uri")
        if not isinstance(installed, dict) or any(not isinstance(installed.get(k), str) or not installed[k]
                                                  for k in required):
            raise InvalidClientSecrets()
        if not installed["auth_uri"].startswith("https://accounts.google.com/") or \
                not installed["token_uri"].startswith("https://oauth2.googleapis.com/"):
            raise InvalidClientSecrets()
        return {"installed": installed}

    def import_client_secrets(self, path: str) -> None:
        try:
            with open(path, "rb") as f:
                raw = f.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise InvalidClientSecrets()
            config = self.validate_client_config(json.loads(raw.decode("utf-8-sig")))
        except IntegrationError:
            raise
        except (OSError, UnicodeError, ValueError, TypeError):
            raise InvalidClientSecrets() from None
        self.vault.set_json(CLIENT_KEY, config)

    def is_configured(self) -> bool:
        return bool(self.vault.get(CLIENT_KEY))

    def _client_config(self) -> dict:
        config = self.vault.get_json(CLIENT_KEY)
        if not config:
            raise CredentialsNotConfigured()
        return self.validate_client_config(config)

    def has_token(self) -> bool:
        return bool(self.vault.get(TOKEN_KEY))

    def _flow(self):
        if self._flow_class is None:
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
            except ImportError:
                raise IntegrationError("As bibliotecas oficiais do Google não estão instaladas. Reinstale o GTA Clipper Studio.",
                                       "unavailable") from None
            self._flow_class = InstalledAppFlow
        try:
            return self._flow_class.from_client_config(
                self._client_config(), SCOPES, autogenerate_code_verifier=True)
        except IntegrationError:
            raise
        except Exception:
            raise InvalidClientSecrets() from None

    def connect(self):
        """Abre o navegador e aguarda somente um callback local validado por state."""
        flow = self._flow()
        state = secrets.token_urlsafe(32)

        class CallbackServer(HTTPServer):
            allow_reuse_address = True

            def __init__(self, address, handler):
                super().__init__(address, handler)
                self.auth_code = None
                self.auth_error = None
                self.callback_done = False

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - assinatura da biblioteca padrão
                parsed = urllib.parse.urlsplit(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                got_state = query.get("state", [""])[0]
                if parsed.path != "/" or not hmac.compare_digest(got_state, state):
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write("Retorno OAuth inválido. Volte ao GTA Clipper Studio.".encode("utf-8"))
                    return
                self.server.callback_done = True
                self.server.auth_error = query.get("error", [None])[0]
                self.server.auth_code = query.get("code", [None])[0]
                self.send_response(200 if self.server.auth_code and not self.server.auth_error else 400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                message = ("Autenticação concluída. Você pode fechar esta janela." if self.server.auth_code
                           else "Autenticação cancelada. Volte ao GTA Clipper Studio.")
                self.wfile.write(f"<!doctype html><meta charset='utf-8'><title>GTA Clipper Studio</title><p>{message}</p>".encode("utf-8"))

            def log_message(self, _format, *args):
                # Não escrever URL de callback ou parâmetros OAuth no log do processo.
                return

        server = None
        try:
            server = CallbackServer(("127.0.0.1", 0), CallbackHandler)
            server.timeout = 0.5
            port = server.server_address[1]
            flow.redirect_uri = f"http://127.0.0.1:{port}/"
            auth_url, _ = flow.authorization_url(state=state, access_type="offline", prompt="consent")
            if not self._browser_open(auth_url):
                raise LoginCancelled()
            deadline = time.monotonic() + 300
            while not server.callback_done and time.monotonic() < deadline:
                server.handle_request()
            if not server.callback_done:
                raise LoginCancelled()
            if server.auth_error:
                if server.auth_error == "access_denied":
                    raise LoginCancelled()
                raise IntegrationError("O Google não concluiu a autenticação. Confira a configuração OAuth e tente novamente.",
                                        "error")
            if not server.auth_code:
                raise LoginCancelled()
            # O state foi comparado em tempo constante antes de trocar o código.
            flow.fetch_token(code=server.auth_code)
            credentials = flow.credentials
            if not credentials or not credentials.token:
                raise AuthenticationRequired()
            token_data = json.loads(credentials.to_json())
            self.vault.set_json(TOKEN_KEY, token_data)
            return credentials
        except IntegrationError:
            raise
        except Exception as exc:
            mapped = self._map_auth_exception(exc)
            raise mapped from None
        finally:
            if server is not None:
                server.server_close()

    def credentials(self):
        token_data = self.vault.get_json(TOKEN_KEY)
        if not token_data:
            raise AuthenticationRequired()
        if self._credentials_class is None:
            try:
                from google.oauth2.credentials import Credentials
            except ImportError:
                raise IntegrationError("As bibliotecas oficiais do Google não estão instaladas. Reinstale o GTA Clipper Studio.",
                                       "unavailable") from None
            self._credentials_class = Credentials
        try:
            credentials = self._credentials_class.from_authorized_user_info(token_data, SCOPES)
            granted = set(getattr(credentials, "scopes", None) or token_data.get("scopes", []))
            if granted and not set(SCOPES).issubset(granted):
                raise PermissionRequired()
            if getattr(credentials, "expired", False) or not getattr(credentials, "valid", False):
                if not getattr(credentials, "refresh_token", None):
                    raise AuthenticationExpired()
                if self._request_factory is None:
                    from google.auth.transport.requests import Request
                    request = Request()
                else:
                    request = self._request_factory()
                credentials.refresh(request)
                self.vault.set_json(TOKEN_KEY, json.loads(credentials.to_json()))
            return credentials
        except (AuthenticationExpired, PermissionRequired, IntegrationError):
            raise
        except Exception as exc:
            mapped = self._map_auth_exception(exc)
            if mapped.status == "expired":
                try:
                    self.vault.delete(TOKEN_KEY)
                except CredentialStoreUnavailable:
                    pass
            raise mapped from None

    def disconnect(self) -> None:
        token = self.vault.get_json(TOKEN_KEY)
        if token and (token.get("refresh_token") or token.get("token")):
            body = urllib.parse.urlencode({"token": token.get("refresh_token") or token["token"]}).encode("ascii")
            request = urllib.request.Request(GOOGLE_REVOKE_URL, data=body,
                                             headers={"Content-Type": "application/x-www-form-urlencoded"})
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    if response.status not in (200, 400):
                        raise IntegrationError("O Google não confirmou a revogação. Tente novamente.", "error")
            except urllib.error.HTTPError as exc:
                if exc.code != 400:  # 400 também significa que o token já não é válido.
                    raise IntegrationError("O Google não confirmou a revogação. Tente novamente.", "error") from None
            except IntegrationError:
                raise
            except Exception:
                raise IntegrationError("Não foi possível conectar ao Google para revogar a autorização.", "error") from None
        self.vault.delete(TOKEN_KEY)

    @staticmethod
    def _map_auth_exception(exc: Exception) -> IntegrationError:
        text = (str(exc) + " " + str(getattr(exc, "args", ""))).lower()
        if "invalid_grant" in text or "token has been expired or revoked" in text:
            return AuthenticationExpired()
        if "access_denied" in text:
            return LoginCancelled()
        if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            return IntegrationError("Não foi possível conectar ao Google. Verifique a conexão com a internet.", "error")
        return IntegrationError("A autenticação do Google falhou. Confira as credenciais OAuth e tente novamente.",
                                "error")
