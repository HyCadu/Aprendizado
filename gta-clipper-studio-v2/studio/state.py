"""Estado compartilhado entre as páginas (configurações, biblioteca, checagens, job atual)."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from .asyncutil import run_async
from .integrations.models import IntegrationError
from .integrations.youtube.auth import YouTubeAuth
from .integrations.youtube.client import YouTubeClient
from .services.publication_service import PublicationService
from .services.publication_storage import PublicationStorage
from .storage import History, Settings, scan_library
from .system import check_all, check_claude_auth, clipper_config, gpu_info

log = logging.getLogger(__name__)


class AppState(QObject):
    clips_changed = Signal()
    checks_changed = Signal()
    auth_changed = Signal()
    gpu_changed = Signal()
    history_changed = Signal()
    job_started = Signal(object)          # dict com dados do job
    job_progress = Signal(str)            # nome da etapa atual (barra de status)
    default_lang_changed = Signal(str)    # idioma padrão da legenda mudou em Configurações
    navigate = Signal(str)                # nome da página
    toast = Signal(str, str)              # texto, tipo
    play_clip = Signal(object)            # Clip
    youtube_changed = Signal()
    publications_changed = Signal()

    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.history = History()
        self.clips = []
        self.checks = []
        self.gpu: dict = {}
        self.cfg: dict = {}
        self.checking = False
        self.job_running = False
        self.auth_status = "checking"
        self.auth_detail = "Verificando a autenticação do Claude Code."
        self._auth_check_id = 0
        self.youtube_status = "checking"
        self.youtube_detail = "Verificando a conexão do YouTube."
        self.youtube_account = None
        self.publication_records = []
        self.publication_error = ""
        self.youtube_auth = None
        self.youtube_client = None
        self.publication_storage = None
        self.publication_service = None
        self._youtube_init_error = ""
        try:
            # O histórico é local e não pode depender do Credential Manager/OAuth.
            self.publication_storage = PublicationStorage()
        except Exception:
            log.exception("Não foi possível inicializar o banco local de publicações.")
            self.publication_error = "Não foi possível abrir o histórico local de publicações."
        try:
            self.youtube_auth = YouTubeAuth()
            self.youtube_client = YouTubeClient(self.youtube_auth)
            if self.publication_storage:
                self.publication_service = PublicationService(self.youtube_client, self.publication_storage)
        except IntegrationError as exc:
            self._youtube_init_error = str(exc)
            self.youtube_status = exc.status
        self.load_publications(emit=False)

    def refresh_clips(self):
        run_async(scan_library, self.settings.library_roots(), on_done=self._clips_done)

    def _clips_done(self, res, err):
        if err is None:
            self.clips = res
        self.clips_changed.emit()

    def refresh_checks(self):
        if self.checking:
            return
        self.checking = True
        self.checks_changed.emit()
        run_async(lambda: (check_all(self.settings["claude_path"]), clipper_config()), on_done=self._checks_done)

    def _checks_done(self, res, err):
        self.checking = False
        if err is None:
            self.checks, self.cfg = res
        self.checks_changed.emit()

    def refresh_auth_status(self):
        self._auth_check_id += 1
        check_id = self._auth_check_id
        claude_path = self.settings["claude_path"]
        self.set_auth_status("checking", "Verificando a autenticação do Claude Code.")
        run_async(check_claude_auth, claude_path,
                  on_done=lambda res, err: self._auth_done(check_id, res, err))

    def _auth_done(self, check_id: int, res, err):
        if check_id != self._auth_check_id:
            return
        if err is not None:
            self.set_auth_status("auth_error", "Não foi possível verificar a autenticação do Claude Code.")
            return
        status, detail = res
        self.set_auth_status(status, detail)

    def set_auth_status(self, status: str, detail: str = ""):
        self.auth_status = status
        self.auth_detail = detail
        self.auth_changed.emit()

    def refresh_gpu(self):
        run_async(gpu_info, on_done=self._gpu_done)

    def _gpu_done(self, res, err):
        self.gpu = res if err is None else {"ok": False, "detail": str(err)}
        self.gpu_changed.emit()

    def check(self, name_prefix: str):
        for c in self.checks:
            if c.name.startswith(name_prefix):
                return c
        return None

    def import_youtube_credentials(self, path: str):
        if not self.youtube_auth:
            raise IntegrationError(self._youtube_init_error or "O armazenamento seguro não está disponível.",
                                    self.youtube_status)
        self.youtube_auth.import_client_secrets(path)

    def _youtube_task(self, operation: str):
        if not self.youtube_auth or not self.youtube_client:
            return self.youtube_status, None, self._youtube_init_error or "Integração do YouTube indisponível."
        try:
            if operation == "connect":
                self.youtube_auth.connect()
            elif operation == "disconnect":
                self.youtube_auth.disconnect()
                return "disconnected", None, "Conta do YouTube desconectada."
            info = self.youtube_client.get_channel()
            return "connected", info, "Conta do YouTube conectada."
        except IntegrationError as exc:
            return exc.status, None, str(exc)
        except Exception:
            return "error", None, "Não foi possível concluir a operação com o YouTube."

    def refresh_youtube(self):
        self.youtube_status = "checking"
        self.youtube_detail = "Verificando a conexão do YouTube."
        self.youtube_changed.emit()
        run_async(self._youtube_task, "refresh", on_done=self._youtube_done)

    def connect_youtube(self):
        self.youtube_status = "checking"
        self.youtube_detail = "Aguardando a autenticação Google no navegador."
        self.youtube_changed.emit()
        run_async(self._youtube_task, "connect", on_done=self._youtube_done)

    def disconnect_youtube(self):
        self.youtube_status = "checking"
        self.youtube_detail = "Revogando a autorização do YouTube."
        self.youtube_changed.emit()
        run_async(self._youtube_task, "disconnect", on_done=self._youtube_done)

    def _youtube_done(self, result, err):
        if err is not None or not result:
            self.youtube_status, self.youtube_account = "error", None
            self.youtube_detail = "Não foi possível verificar a conexão do YouTube."
        else:
            self.youtube_status, self.youtube_account, self.youtube_detail = result
        self.youtube_changed.emit()

    def load_publications(self, emit: bool = True):
        """Carrega o histórico local imediatamente; não depende de OAuth ou rede."""
        if not self.publication_storage:
            self.publication_records = []
            if not self.publication_error:
                self.publication_error = "O armazenamento local do histórico está indisponível."
            if emit:
                self.publications_changed.emit()
            return
        try:
            self.publication_records = self.publication_storage.list_recent()
            self.publication_error = ""
        except Exception:
            log.exception("Não foi possível carregar o histórico local de publicações.")
            self.publication_error = "Não foi possível ler o histórico local de publicações."
        if emit:
            self.publications_changed.emit()

    def refresh_publications(self, reconcile: bool = False):
        # Mostra o que já está salvo antes de consultar a API. Assim, falhas de rede
        # ou uma conta desconectada não deixam a seção vazia.
        self.load_publications()
        if not reconcile or not self.publication_service:
            return
        run_async(self.publication_service.reconcile, on_done=self._publications_done)

    def _publications_done(self, result, err):
        if err is None and result is not None:
            self.publication_records = result
            self.publication_error = ""
        elif self.publication_storage:
            try:
                self.publication_records = self.publication_storage.list_recent()
                self.publication_error = ""
            except Exception:
                log.exception("Não foi possível recarregar o histórico após falha na reconciliação.")
                self.publication_error = "Não foi possível ler o histórico local de publicações."
        self.publications_changed.emit()
