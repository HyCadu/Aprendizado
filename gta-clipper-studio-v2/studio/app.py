from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from . import APP_NAME, __version__
from . import theme as T
from .core import AUTH_REQUIRED_MESSAGE
from .pages.create import CreatePage
from .pages.integrations import Integrations
from .pages.library import Library
from .pages.settings_page import Settings
from .state import AppState
from .widgets import AppMark, FadeStack, StatusBar, Toast, TopNav, glyph, icon_font, label

PAGES = ["create", "library", "integrations", "settings"]
TITLES = ["Criar cortes", "Biblioteca", "Integrações", "Configurações"]


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, s, s)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.PRIMARY))
        p.drawRoundedRect(r, s * 0.24, s * 0.24)
        p.setFont(icon_font(int(s * 0.56)))
        p.setPen(QColor(T.ON_PRIMARY))
        p.drawText(r, Qt.AlignCenter, glyph("cut"))
        p.end()
        icon.addPixmap(pm)
    return icon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1280, 840)
        self.setMinimumSize(900, 620)
        self.state = st = AppState()

        root = QWidget()
        root.setObjectName("Root")
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # barra superior: marca + abas
        top = QFrame()
        top.setObjectName("TopBar")
        th = QHBoxLayout(top)
        th.setContentsMargins(T.SP5, 0, T.SP5, 0)
        th.setSpacing(T.SP3)
        th.addWidget(AppMark(24))
        th.addWidget(label("GTA Clipper Studio", "BrandName"))
        th.addSpacing(T.SP6)
        self.nav = TopNav()
        for t in TITLES:
            self.nav.add(t)
        th.addWidget(self.nav)
        th.addStretch(1)
        v.addWidget(top)

        self.stack = FadeStack()
        v.addWidget(self.stack, 1)
        self.status = StatusBar()
        v.addWidget(self.status)
        self.setCentralWidget(root)

        self.create = CreatePage(st)
        self.library = Library(st)
        self.integrations = Integrations(st)
        self.settings = Settings(st)
        self.pages = [self.create, self.library, self.integrations, self.settings]
        for p in self.pages:
            self.stack.addWidget(p)
        self.nav.changed.connect(self._go)
        self.toast = Toast(root)

        st.navigate.connect(self.goto)
        st.toast.connect(self.toast.show_msg)
        st.play_clip.connect(self._open_clip)
        st.job_started.connect(self._start_job)
        st.job_progress.connect(lambda step: self.status.set_job(f"Processando · {step}"))
        st.checks_changed.connect(self._update_status)
        st.auth_changed.connect(self._update_auth_status)
        st.youtube_changed.connect(self._update_youtube_status)
        self.status.clicked_issue.connect(lambda: self.goto("settings"))
        self.status.clicked_youtube.connect(lambda: self.goto("integrations"))
        self.create.finished.connect(self._job_done)

        self.nav.select(0)
        self._update_auth_status()
        self._update_youtube_status()
        QTimer.singleShot(50, st.refresh_checks)
        QTimer.singleShot(55, st.refresh_auth_status)
        QTimer.singleShot(56, st.refresh_youtube)
        QTimer.singleShot(60, st.refresh_gpu)
        QTimer.singleShot(70, st.refresh_clips)
        QTimer.singleShot(80, st.history_changed.emit)

    # ------------------------------------------------------------ navegação
    def goto(self, name: str):
        self.nav.select(PAGES.index(name))

    def _go(self, i: int):
        prev = self.stack.currentWidget()
        if prev is not None and prev is not self.pages[i]:
            prev.on_hide()
        self.stack.set_index(i)
        self.pages[i].on_show()

    def _open_clip(self, clip):
        self.goto("library")
        self.library.open_clip(clip)

    # ------------------------------------------------------------ status
    def _update_status(self):
        st = self.state
        if st.checking and not st.checks:
            self.status.set_system(T.DIM, "Verificando o sistema…")
            return
        bad = [c for c in st.checks if c.required and not c.ok]
        if bad:
            n = len(bad)
            self.status.set_system(T.WARNING, f"{n} pendência{'s' if n > 1 else ''} · ver Configurações")
        else:
            self.status.set_system(T.SUCCESS, "Sistema pronto")

    def _update_auth_status(self):
        labels = {
            "connected": "Claude Code conectado",
            "disconnected": "Claude Code desconectado",
            "checking": "Verificando Claude Code…",
            "unavailable": "Claude Code indisponível",
            "auth_error": "Erro de autenticação",
        }
        self.status.set_auth_status(self.state.auth_status, labels.get(self.state.auth_status, "Claude Code"))

    def _update_youtube_status(self):
        labels = {"connected": "YouTube conectado", "disconnected": "YouTube desconectado",
                  "checking": "Verificando YouTube…", "unavailable": "YouTube indisponível",
                  "expired": "Reconectar YouTube", "error": "Erro na conexão YouTube"}
        self.status.set_youtube_status(self.state.youtube_status,
                                       labels.get(self.state.youtube_status, "YouTube"))

    # ------------------------------------------------------------ jobs
    def _start_job(self, job: dict):
        if self.create.is_running():
            self.toast.show_msg("Já existe um processamento em andamento.", "warn")
            return
        if self.state.auth_status != "connected":
            message = (AUTH_REQUIRED_MESSAGE if self.state.auth_status in ("disconnected", "auth_error") else
                       "Aguarde a verificação do Claude Code ou confira a autenticação em Configurações.")
            self.toast.show_msg(message, "error")
            return
        if not self.create.start(job):
            return
        self.state.job_running = True
        self.nav.set_activity(PAGES.index("create"), True)
        self.status.set_job("Processando · iniciando")
        self.state.history.add({"url": job["url"], "platform": job["platform"], "clips_req": job["clips"],
                                "legenda": job.get("legenda"), "status": "rodando",
                                "when": time.strftime("%Y-%m-%d %H:%M")})
        self.state.history_changed.emit()
        self.goto("create")

    def _job_done(self, status: str, job: dict):
        self.state.job_running = False
        self.nav.set_activity(PAGES.index("create"), False)
        text = {"ok": "Concluído", "cancelado": "Cancelado", "erro": "Erro no processamento",
                "auth_error": "Erro de autenticação"}[status]
        color = {"ok": T.SUCCESS, "cancelado": T.WARNING, "erro": T.ERROR,
                 "auth_error": T.ERROR}[status]
        self.status.set_job(text, color, pulse=False)
        QTimer.singleShot(8000, lambda: None if self.state.job_running else self.status.set_job(None))
        before = {str(c.path) for c in self.state.clips}

        def after_scan():
            self.state.clips_changed.disconnect(after_scan)
            new = [c for c in self.state.clips if str(c.path) not in before]
            if status == "ok":
                self.create.show_results(new)
            elif status == "auth_error" and new:
                self.create.show_results(new, show_empty=False)
            title = new[0].video_title if new else ""
            history_update = {"status": status, "elapsed": job.get("elapsed"), "log": job.get("log")}
            if status != "auth_error" or new:
                history_update.update(clips=len(new), title=title)
            if status == "auth_error":
                history_update["error"] = job.get("error") or AUTH_REQUIRED_MESSAGE
            self.state.history.update_last(**history_update)
            self.state.history_changed.emit()
            msg = {"ok": f"Concluído: {len(new)} clipe(s) novo(s).", "cancelado": "Processamento cancelado.",
                   "erro": "O processamento terminou com erro. Veja os logs.",
                   "auth_error": AUTH_REQUIRED_MESSAGE}[status]
            kind = {"ok": "info", "cancelado": "warn", "erro": "error", "auth_error": "error"}[status]
            self.toast.show_msg(msg, kind)
            QApplication.alert(self)

        self.state.clips_changed.connect(after_scan)
        self.state.refresh_clips()

    def closeEvent(self, e):
        if self.create.is_running():
            r = QMessageBox.question(
                self, "Processamento em andamento",
                "Há um corte rodando. Fechar o app cancela o processamento (nenhum arquivo é apagado).\n\n"
                "Fechar mesmo assim?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                e.ignore()
                return
            self.create.cancel()
        self.library.on_hide()
        e.accept()


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GTAClipperStudio.V2")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    f = QFont(T.FONT_FAMILY)
    if not f.exactMatch():
        f = QFont("Segoe UI")
    f.setPixelSize(T.FS_MD)
    app.setFont(f)
    app.setStyleSheet(T.QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
