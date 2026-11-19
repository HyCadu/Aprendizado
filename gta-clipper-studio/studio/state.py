"""Estado compartilhado entre as páginas (configurações, biblioteca, checagens, job atual)."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from .asyncutil import run_async
from .storage import History, Settings, scan_library
from .system import check_all, clipper_config, gpu_info


class AppState(QObject):
    clips_changed = Signal()
    checks_changed = Signal()
    gpu_changed = Signal()
    history_changed = Signal()
    job_started = Signal(object)          # dict com dados do job
    navigate = Signal(str)                # nome da página
    toast = Signal(str, str)              # texto, tipo
    play_clip = Signal(object)            # Clip

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
