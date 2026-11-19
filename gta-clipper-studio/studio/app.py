from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QMessageBox, QWidget

from . import APP_NAME, __version__
from . import theme as T
from .pages.dashboard import Dashboard
from .pages.library import Library
from .pages.new_job import NewJob
from .pages.player import play
from .pages.processing import Processing
from .pages.settings_page import Settings
from .state import AppState
from .widgets import FadeStack, Sidebar, SunsetBackground, Toast

PAGES = ["dashboard", "new", "processing", "library", "settings"]


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, s, s)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(T.ORANGE))
        g.setColorAt(0.5, QColor(T.PINK))
        g.setColorAt(1, QColor(T.PURPLE))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, s * 0.24, s * 0.24)
        path = QPainterPath()
        path.moveTo(s * 0.36, s * 0.25)
        path.lineTo(s * 0.77, s * 0.5)
        path.lineTo(s * 0.36, s * 0.75)
        path.closeSubpath()
        p.setBrush(QColor(T.BG))
        p.drawPath(path)
        p.end()
        icon.addPixmap(pm)
    return icon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        # Cabe em telas pequenas (notebook 1366x768, 125-150% de escala): começa com até 90% da área livre.
        self.setMinimumSize(560, 460)
        scr = QGuiApplication.primaryScreen()
        if scr is not None:
            av = scr.availableGeometry()
            self.resize(min(1360, int(av.width() * 0.9)), min(860, int(av.height() * 0.9)))
        else:
            self.resize(1360, 860)
        self.state = st = AppState()

        root = SunsetBackground()
        root.setObjectName("Root")
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.sidebar = Sidebar()
        h.addWidget(self.sidebar)
        self.stack = FadeStack()
        h.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.dashboard = Dashboard(st)
        self.new = NewJob(st)
        self.processing = Processing(st)
        self.library = Library(st)
        self.settings = Settings(st)
        self.pages = [self.dashboard, self.new, self.processing, self.library, self.settings]
        for icon, text, page in (("home", "Dashboard", self.dashboard), ("add", "Novo corte", self.new),
                                 ("sync", "Processamento", self.processing), ("library", "Biblioteca", self.library),
                                 ("settings", "Configurações", self.settings)):
            self.sidebar.add(icon, text)
            self.stack.addWidget(page)
        self.sidebar.footer.setText(f"v{__version__} · Nada é publicado automaticamente.")
        self.sidebar.changed.connect(self._go)
        self.toast = Toast(root)

        st.navigate.connect(lambda name: self.goto(name))
        st.toast.connect(self.toast.show_msg)
        st.play_clip.connect(lambda c: play(c, self))
        st.job_started.connect(self._start_job)
        self.processing.finished.connect(self._job_done)

        self.sidebar.select(0)
        QTimer.singleShot(50, st.refresh_checks)
        QTimer.singleShot(60, st.refresh_gpu)
        QTimer.singleShot(70, st.refresh_clips)
        QTimer.singleShot(80, st.history_changed.emit)

    # ------------------------------------------------------------ navegação
    def goto(self, name: str):
        self.sidebar.select(PAGES.index(name))

    def _go(self, i: int):
        prev = self.stack.currentWidget()
        if prev is not None and hasattr(prev, "on_hide"):
            prev.on_hide()
        self.stack.set_index(i)
        self.pages[i].on_show()

    # ------------------------------------------------------------ jobs
    def _start_job(self, job: dict):
        if self.processing.is_running():
            self.toast.show_msg("Já existe um processamento em andamento.", "warn")
            return
        if not self.processing.start(job):
            return
        self.state.job_running = True
        self.new.set_running(True)
        self.sidebar.buttons[PAGES.index("processing")].set_activity(True)
        self.state.history.add({"url": job["url"], "platform": job["platform"], "clips_req": job["clips"],
                                "status": "rodando", "when": time.strftime("%Y-%m-%d %H:%M")})
        self.state.history_changed.emit()
        self.goto("processing")

    def _job_done(self, status: str, job: dict):
        self.state.job_running = False
        self.new.set_running(False)
        self.sidebar.buttons[PAGES.index("processing")].set_activity(False)
        before = {str(c.path) for c in self.state.clips}

        def after_scan():
            self.state.clips_changed.disconnect(after_scan)
            new = [c for c in self.state.clips if str(c.path) not in before]
            title = new[0].video_title if new else ""
            self.state.history.update_last(status=status, clips=len(new), title=title,
                                           elapsed=job.get("elapsed"), log=job.get("log"))
            self.state.history_changed.emit()
            msg = {"ok": f"Concluído: {len(new)} clipe(s) novo(s).", "cancelado": "Processamento cancelado.",
                   "erro": "O processamento terminou com erro. Veja o log."}[status]
            self.toast.show_msg(msg, {"ok": "info", "cancelado": "warn", "erro": "error"}[status])
            QApplication.alert(self)

        self.state.clips_changed.connect(after_scan)
        self.state.refresh_clips()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.sidebar.set_compact(e.size().width() < 1000)

    def closeEvent(self, e):
        if self.processing.is_running():
            r = QMessageBox.question(
                self, "Processamento em andamento",
                "Há um corte rodando. Fechar o app cancela o processamento (nenhum arquivo é apagado).\n\n"
                "Fechar mesmo assim?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                e.ignore()
                return
            self.processing.cancel()
        e.accept()


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("GTAClipperStudio.App")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    f = QFont("Segoe UI Variable Text")
    f.setPixelSize(13)
    app.setFont(f)
    app.setStyleSheet(T.QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
