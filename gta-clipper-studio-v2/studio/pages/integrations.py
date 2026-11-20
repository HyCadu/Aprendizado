"""Conexão OAuth com o YouTube e histórico local de publicações."""
from __future__ import annotations

import urllib.request

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import publishing as P
from .. import theme as T
from ..asyncutil import run_async
from ..widgets import Badge, BrandLogo, EmptyState, SectionHeader, button, clear_layout, label, panel
from .common import Page

STATUS_TEXT = {
    "queued": "Aguardando envio", "uploading": "Enviando", "processing": "Processando no YouTube",
    "scheduled": "Agendado", "published": "Publicado", "private": "Privado",
    "unlisted": "Não listado", "cancelled": "Cancelado", "failed": "Falhou", "unknown": "Status desconhecido",
}
STATUS_COLOR = {"queued": T.WARNING, "uploading": T.PRIMARY, "processing": T.INFO, "scheduled": T.INFO,
                "published": T.SUCCESS, "private": T.MUTED, "unlisted": T.MUTED, "cancelled": T.MUTED,
                "failed": T.ERROR, "unknown": T.WARNING}


def _load_avatar(url: str) -> bytes:
    if not url.startswith("https://"):
        return b""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "GTAClipperStudio/1"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.read(2 * 1024 * 1024)
    except Exception:
        return b""


def _number(value):
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "—"


class Integrations(Page):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._avatar_url = ""
        self._avatar_data = b""
        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(label("Integrações", "H1"))
        head.addWidget(label("Conecte seu canal e acompanhe publicações feitas pela YouTube Data API.", "Muted"))
        self.body.addLayout(head)

        self.youtube_card = panel("Panel")
        self.youtube_layout = QVBoxLayout(self.youtube_card)
        self.youtube_layout.setContentsMargins(T.SP5, T.SP5, T.SP5, T.SP5)
        self.youtube_layout.setSpacing(T.SP3)
        self.body.addWidget(self.youtube_card)

        future = QGridLayout()
        future.setSpacing(T.SP3)
        for index, platform in enumerate(p for p in P.PLATFORMS if p.key != "youtube"):
            future.addWidget(self._future_card(platform), 0, index)

        history_panel = panel("Panel")
        hv = QVBoxLayout(history_panel)
        hv.setContentsMargins(T.SP4, T.SP4, T.SP4, T.SP4)
        top = QHBoxLayout()
        top.addWidget(SectionHeader("Publicações", "Envios, agendamentos, resultados e links do YouTube."), 1)
        refresh = button("Atualizar", "refresh", "Ghost")
        refresh.clicked.connect(lambda: state.refresh_publications(reconcile=True))
        top.addWidget(refresh)
        hv.addLayout(top)
        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(["Enviado", "Título", "Canal", "Status", "YouTube"])
        self.history.verticalHeader().setVisible(False)
        self.history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history.setSelectionBehavior(QTableWidget.SelectRows)
        self.history.setAlternatingRowColors(False)
        self.history.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.history.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.history.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.history.cellClicked.connect(self._open_history_link)
        self.history.setMinimumHeight(170)
        hv.addWidget(self.history)
        self.empty_history = EmptyState("history", "Nenhuma publicação ainda", "Os envios e agendamentos aparecerão aqui.", compact=True)
        hv.addWidget(self.empty_history)
        self.body.addWidget(history_panel)
        self.body.addWidget(SectionHeader("Outras plataformas", "Instagram, TikTok e Facebook poderão ser conectados em uma etapa futura."))
        self.body.addLayout(future)
        self.body.addStretch(1)

        state.youtube_changed.connect(self._youtube_changed)
        state.publications_changed.connect(self._render_history)
        self._render_youtube()
        self._render_history()

    @staticmethod
    def _future_card(platform):
        box = panel("PanelFlat")
        v = QVBoxLayout(box)
        v.setContentsMargins(T.SP3, T.SP3, T.SP3, T.SP3)
        top = QHBoxLayout()
        top.addWidget(BrandLogo(platform.key, 26))
        top.addStretch(1)
        top.addWidget(Badge("Em breve", T.MUTED))
        v.addLayout(top)
        v.addWidget(label(platform.name, "H3"))
        v.addWidget(label(platform.description, "Dim", True))
        return box

    def on_show(self):
        self.state.refresh_youtube()
        self.state.refresh_publications(reconcile=self.state.youtube_status == "connected")

    def _youtube_changed(self):
        self._render_youtube()
        if self.state.youtube_status == "connected":
            self.state.refresh_publications(reconcile=True)

    def _configured(self) -> bool:
        try:
            return bool(self.state.youtube_auth and self.state.youtube_auth.is_configured())
        except Exception:
            return False

    def _render_youtube(self):
        clear_layout(self.youtube_layout)
        status = self.state.youtube_status
        account = self.state.youtube_account if status == "connected" else None
        color = {"connected": T.SUCCESS, "checking": T.PRIMARY, "disconnected": T.WARNING,
                 "expired": T.WARNING, "unavailable": T.MUTED, "error": T.ERROR}.get(status, T.MUTED)
        status_text = {"connected": "Conta conectada", "checking": "Verificando conexão…",
                       "disconnected": "Desconectado", "expired": "Autorização expirada",
                       "unavailable": "Indisponível", "error": "Erro na conexão"}.get(status, "Desconectado")
        top = QHBoxLayout()
        top.addWidget(BrandLogo("youtube", 30))
        top.addWidget(label("YouTube Shorts", "H2"), 1)
        top.addWidget(Badge(status_text, color))
        self.youtube_layout.addLayout(top)
        self.youtube_layout.addWidget(label("Publicação de vídeos pela API oficial do YouTube.", "Dim"))

        configured = self._configured()
        if account:
            self._render_connected(account)
        else:
            self.youtube_layout.addWidget(label(
                "Credenciais OAuth configuradas" if configured else "Credenciais OAuth não configuradas",
                "Success" if configured else "Dim"))
            if self.state.youtube_detail and status not in ("checking", "disconnected"):
                self.youtube_layout.addWidget(label(self.state.youtube_detail, "Error" if status == "error" else "Dim", True))
            controls = QHBoxLayout()
            self.import_button = button("Importar credenciais", "folder")
            self.import_button.clicked.connect(self._import_credentials)
            self.connect_button = button("Conectar conta", "open", "Primary")
            self.connect_button.setEnabled(configured and status != "checking")
            self.connect_button.setToolTip("Importe client_secrets.json do tipo Aplicativo para computador." if not configured else "")
            self.connect_button.clicked.connect(self.state.connect_youtube)
            controls.addWidget(self.import_button)
            controls.addWidget(self.connect_button)
            instructions = button("Configuração OAuth", None, "Ghost")
            instructions.clicked.connect(lambda: QDesktopServices.openUrl(
                QUrl("https://developers.google.com/identity/protocols/oauth2/native-app")))
            controls.addWidget(instructions)
            controls.addStretch(1)
            self.youtube_layout.addLayout(controls)

    def _render_connected(self, account: dict):
        thumbnail = account.get("thumbnail", "")
        if thumbnail and thumbnail != self._avatar_url:
            self._avatar_url, self._avatar_data = thumbnail, b""
            run_async(_load_avatar, thumbnail,
                      on_done=lambda data, err, url=thumbnail: self._avatar_loaded(url, data, err))
        if thumbnail == self._avatar_url and self._avatar_data:
            account["thumbnail_data"] = self._avatar_data
        row = QHBoxLayout()
        avatar = QLabel()
        avatar.setFixedSize(64, 64)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setObjectName("PanelFlat")
        pix = QPixmap()
        if account.get("thumbnail_data"):
            pix.loadFromData(account["thumbnail_data"])
        if not pix.isNull():
            avatar.setPixmap(pix.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            avatar.setText("▶")
            avatar.setStyleSheet(f"color: {T.YOUTUBE_RED}; font-size: 26px;")
        row.addWidget(avatar)
        avatar.setToolTip("Foto do canal autenticado")
        details = QVBoxLayout()
        details.addWidget(label(account.get("title", "Canal do YouTube"), "H3"))
        details.addWidget(label(f"ID do canal: {account.get('id', '')}", "Dim"))
        if account.get("custom_url"):
            details.addWidget(label(account["custom_url"], "Dim"))
        row.addLayout(details, 1)
        stats = QVBoxLayout()
        stats.addWidget(label(f"{_number(account.get('subscribers'))} inscritos", "Label"))
        stats.addWidget(label(f"{_number(account.get('videos'))} vídeos", "Label"))
        stats.addWidget(label(f"{_number(account.get('views'))} visualizações", "Dim"))
        row.addLayout(stats)
        self.youtube_layout.addLayout(row)
        links = QHBoxLayout()
        open_channel = button("Abrir canal", "open")
        open_channel.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(account.get("url", ""))))
        studio = button("Abrir YouTube Studio", "open", "Primary")
        studio.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://studio.youtube.com/")))
        refresh = button("Atualizar informações", "refresh", "Ghost")
        refresh.clicked.connect(self.state.refresh_youtube)
        reconnect = button("Reconectar", None, "Ghost")
        reconnect.clicked.connect(self.state.connect_youtube)
        disconnect = button("Desconectar", None, "Danger")
        disconnect.clicked.connect(self._disconnect)
        for control in (open_channel, studio, refresh, reconnect, disconnect):
            links.addWidget(control)
        links.addStretch(1)
        self.youtube_layout.addLayout(links)

    def _avatar_loaded(self, url: str, data, error):
        if url != self._avatar_url:
            return
        self._avatar_data = data if error is None and data else b""
        if self.state.youtube_account and self.state.youtube_account.get("thumbnail") == url:
            self.state.youtube_account["thumbnail_data"] = self._avatar_data
            self._render_youtube()

    def _import_credentials(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar credenciais OAuth", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.state.import_youtube_credentials(path)
        except Exception as exc:
            QMessageBox.warning(self, "Credenciais OAuth", str(exc))
            return
        QMessageBox.information(self, "Credenciais importadas", "As credenciais foram guardadas no cofre seguro do sistema.")
        self._render_youtube()

    def _disconnect(self):
        answer = QMessageBox.question(self, "Desconectar YouTube",
                                      "Revogar a autorização desta conta e remover o token do cofre do Windows?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.state.disconnect_youtube()

    def _render_history(self):
        records = self.state.publication_records or []
        if self.state.publication_error:
            self.empty_history.set("error", "Histórico indisponível", self.state.publication_error, T.ERROR)
        else:
            self.empty_history.set("history", "Nenhuma publicação ainda",
                                   "Os envios e agendamentos aparecerão aqui.")
        self.history.setRowCount(len(records))
        for row, item in enumerate(records):
            uploaded = item.get("uploaded_at") or item.get("created_at", "")
            if uploaded.endswith("Z"):
                uploaded = uploaded[:-1].replace("T", " ")
            if len(uploaded) > 16:
                uploaded = uploaded[:16]
            title = item.get("title", "")
            if item.get("error"):
                title_item = QTableWidgetItem(title)
                title_item.setToolTip(item["error"])
            else:
                title_item = QTableWidgetItem(title)
            self.history.setItem(row, 0, QTableWidgetItem(uploaded))
            self.history.setItem(row, 1, title_item)
            self.history.setItem(row, 2, QTableWidgetItem(item.get("channel_name", "")))
            status = item.get("status", "unknown")
            status_item = QTableWidgetItem(STATUS_TEXT.get(status, status))
            status_item.setForeground(QColor(STATUS_COLOR.get(status, T.MUTED)))
            status_item.setData(Qt.UserRole, STATUS_COLOR.get(status, T.MUTED))
            self.history.setItem(row, 3, status_item)
            link_item = QTableWidgetItem("Abrir vídeo" if item.get("url") else "—")
            link_item.setData(Qt.UserRole, item.get("url", ""))
            self.history.setItem(row, 4, link_item)
        self.empty_history.setVisible(not records)
        self.history.setVisible(bool(records))

    def _open_history_link(self, row: int, column: int):
        if column == 4:
            url = self.history.item(row, column).data(Qt.UserRole)
            if url:
                QDesktopServices.openUrl(QUrl(url))
