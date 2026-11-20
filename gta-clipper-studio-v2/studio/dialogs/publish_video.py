"""Revisão explícita dos metadados antes de publicar um clipe no YouTube."""
from __future__ import annotations

from PySide6.QtCore import Qt, QDateTime, Signal, QObject, QRunnable, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QProgressBar, QRadioButton, QScrollArea,
                               QVBoxLayout, QWidget)

from .. import theme as T
from ..asyncutil import run_async
from ..integrations.base import PublishRequest
from ..integrations.models import IntegrationError
from ..integrations.youtube.validators import (parse_post_metadata, probe_video, short_eligibility_text,
                                               validate_publish_request)
from ..storage import fmt_duration, fmt_size
from ..widgets import button, label, panel

CATEGORIES = [("20", "Jogos"), ("24", "Entretenimento"), ("22", "Pessoas e blogs"),
              ("23", "Comédia"), ("27", "Educação"), ("28", "Ciência e tecnologia")]
VISIBILITY = [("private", "Privado"), ("unlisted", "Não listado"), ("public", "Público")]


def _words(text: str) -> list[str]:
    return [word.strip() for word in text.replace("\n", ",").split(",") if word.strip()]


class PublishVideoDialog(QDialog):
    def __init__(self, clip, account: dict, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.account = account or {}
        self.request: PublishRequest | None = None
        self.media_info = {}
        self.setWindowTitle("Publicar no YouTube")
        self.setMinimumSize(640, 700)
        self.resize(700, 780)

        defaults = parse_post_metadata(clip.post_md, {
            "title": clip.title, "description": clip.caption,
            "hashtags": clip.hashtags,
        })
        outer = QVBoxLayout(self)
        outer.setContentsMargins(T.SP5, T.SP4, T.SP5, T.SP4)
        outer.setSpacing(T.SP3)
        outer.addWidget(label("Revisar publicação", "H2"))
        outer.addWidget(label("Confira o destino e todos os metadados. O vídeo só será enviado depois de confirmar.",
                              "Dim", True))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, T.SP2, 0)
        body.setSpacing(T.SP3)
        summary = panel("PanelFlat")
        sh = QHBoxLayout(summary)
        sh.setContentsMargins(T.SP3, T.SP3, T.SP3, T.SP3)
        self.preview = QLabel()
        self.preview.setFixedSize(132, 76)
        self.preview.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(str(clip.sheet))
        if not pixmap.isNull():
            self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.preview.setText("Prévia indisponível")
            self.preview.setObjectName("Muted")
        sh.addWidget(self.preview)
        info = QVBoxLayout()
        info.addWidget(label(str(self.account.get("title") or "Canal conectado"), "H3"))
        source = label(f"{clip.path.name} · {fmt_duration(clip.duration)} · {fmt_size(clip.size)}", "Dim", True)
        source.setToolTip(str(clip.path))
        info.addWidget(source)
        self.resolution = label("Resolução: verificando…", "Dim")
        info.addWidget(self.resolution)
        self.eligibility = label("Elegibilidade para Shorts: verificando…", "Dim", True)
        info.addWidget(self.eligibility)
        sh.addLayout(info, 1)
        body.addWidget(summary)
        run_async(probe_video, str(clip.path), on_done=self._probe_done)

        form_box = panel("PanelFlat")
        form = QFormLayout(form_box)
        form.setContentsMargins(T.SP3, T.SP3, T.SP3, T.SP3)
        form.setVerticalSpacing(T.SP2)
        self.title_edit = QLineEdit(defaults["title"])
        self.title_count = label("", "Dim")
        title_row = QHBoxLayout()
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(self.title_count)
        self.title_edit.textChanged.connect(lambda text: self.title_count.setText(f"{len(text)}/100"))
        self.title_count.setText(f"{len(self.title_edit.text())}/100")
        form.addRow("Título", title_row)
        self.description_edit = QPlainTextEdit(defaults["description"])
        self.description_edit.setPlaceholderText("Descrição do vídeo")
        self.description_edit.setMaximumHeight(104)
        form.addRow("Descrição", self.description_edit)
        tags = " ".join(defaults["hashtags"])
        self.hashtags_edit = QLineEdit(tags)
        self.hashtags_edit.setPlaceholderText("#gta #shorts")
        form.addRow("Hashtags", self.hashtags_edit)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("gta, gameplay, melhores momentos")
        form.addRow("Tags", self.tags_edit)
        self.category = QComboBox()
        for value, name in CATEGORIES:
            self.category.addItem(name, value)
        form.addRow("Categoria", self.category)
        self.language = QComboBox()
        for code, name in (("pt", "Português"), ("en", "Inglês"), ("es", "Espanhol"), ("", "Não definido")):
            self.language.addItem(name, code)
        form.addRow("Idioma", self.language)
        body.addWidget(form_box)

        audience = QGroupBox("Público infantil — escolha uma opção")
        ah = QHBoxLayout(audience)
        self.kids_yes = QRadioButton("Sim, é conteúdo para crianças")
        self.kids_no = QRadioButton("Não é conteúdo para crianças")
        group = QButtonGroup(audience)
        group.setExclusive(True)
        group.addButton(self.kids_yes)
        group.addButton(self.kids_no)
        ah.addWidget(self.kids_yes)
        ah.addWidget(self.kids_no)
        body.addWidget(audience)
        self.synthetic = QCheckBox("Este vídeo contém conteúdo alterado ou sintético que parece real")
        body.addWidget(self.synthetic)

        publication = QGroupBox("Publicação")
        pv = QVBoxLayout(publication)
        now_row = QHBoxLayout()
        self.publish_now = QRadioButton("Publicar agora")
        self.publish_now.setChecked(True)
        self.publish_later = QRadioButton("Agendar publicação")
        schedule_group = QButtonGroup(publication)
        schedule_group.addButton(self.publish_now)
        schedule_group.addButton(self.publish_later)
        now_row.addWidget(self.publish_now)
        now_row.addWidget(self.publish_later)
        now_row.addStretch(1)
        pv.addLayout(now_row)
        self.schedule_at = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.schedule_at.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.schedule_at.setCalendarPopup(True)
        self.schedule_at.setMinimumDateTime(QDateTime.currentDateTime().addSecs(60))
        self.schedule_at.setEnabled(False)
        pv.addWidget(self.schedule_at)
        self.publish_later.toggled.connect(self._set_scheduled)
        vis_row = QHBoxLayout()
        vis_row.addWidget(label("Visibilidade", "Label"))
        self.visibility = QComboBox()
        for value, name in VISIBILITY:
            self.visibility.addItem(name, value)
        self.visibility.setCurrentIndex(0)  # privado por padrão
        vis_row.addWidget(self.visibility)
        vis_row.addStretch(1)
        pv.addLayout(vis_row)
        self.schedule_note = label("O agendamento do YouTube é enviado como privado e será publicado no horário escolhido.",
                                   "Dim", True)
        self.schedule_note.setVisible(False)
        pv.addWidget(self.schedule_note)
        body.addWidget(publication)
        self.rights = QCheckBox("Confirmo que tenho autorização para publicar este conteúdo.")
        body.addWidget(self.rights)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        buttons = QDialogButtonBox()
        self.cancel_button = buttons.addButton("Cancelar", QDialogButtonBox.RejectRole)
        self.send_button = buttons.addButton("Enviar Short", QDialogButtonBox.AcceptRole)
        self.send_button.setObjectName("Primary")
        self.cancel_button.clicked.connect(self.reject)
        self.send_button.clicked.connect(self._submit)
        outer.addWidget(buttons)

    def _probe_done(self, result, error):
        if error or not result:
            return
        self.media_info = result
        width, height = result.get("width", 0), result.get("height", 0)
        if width and height:
            self.resolution.setText(f"Resolução: {width} × {height}")
        else:
            self.resolution.setText("Resolução: indisponível (ffprobe não encontrado)")
        self.eligibility.setText("Shorts: " + short_eligibility_text(result))

    def _set_scheduled(self, enabled: bool):
        self.schedule_at.setEnabled(enabled)
        self.schedule_note.setVisible(enabled)
        self.visibility.setEnabled(not enabled)
        if enabled:
            private_index = self.visibility.findData("private")
            if private_index >= 0:
                self.visibility.setCurrentIndex(private_index)

    def _submit(self):
        kids = True if self.kids_yes.isChecked() else False if self.kids_no.isChecked() else None
        schedule = None
        if self.publish_later.isChecked():
            dt = self.schedule_at.dateTime().toPython()
            if dt.tzinfo is None:
                dt = dt.astimezone()
            schedule = dt.isoformat()
        self.request = PublishRequest(
            clip_path=str(self.clip.path), platform="youtube", title=self.title_edit.text().strip(),
            description=self.description_edit.toPlainText(), hashtags=_words(self.hashtags_edit.text()),
            tags=_words(self.tags_edit.text()), category_id=str(self.category.currentData()),
            language=str(self.language.currentData() or ""), made_for_kids=kids,
            contains_synthetic_media=self.synthetic.isChecked(), privacy_status=str(self.visibility.currentData()),
            scheduled_for=schedule, rights_confirmed=self.rights.isChecked(),
            clip_id=str(self.clip.path), channel_id=str(self.account.get("id") or ""))
        try:
            validate_publish_request(self.request)
        except IntegrationError as exc:
            QMessageBox.warning(self, "Confira a publicação", str(exc))
            return
        super().accept()


class _UploadSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object, object)


class UploadWorker(QRunnable):
    def __init__(self, service, request: PublishRequest):
        super().__init__()
        self.service = service
        self.request = request
        self.cancel_event = __import__("threading").Event()
        self.signals = _UploadSignals()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            record = self.service.publish(self.request,
                                         progress=lambda sent, total, stage: self.signals.progress.emit(sent, total, stage),
                                         cancelled=self.cancel_event.is_set)
            self.signals.finished.emit(record, None)
        except IntegrationError as exc:
            self.signals.finished.emit(None, str(exc))
        except Exception:
            self.signals.finished.emit(None, "Ocorreu um erro inesperado durante o envio. Confira o histórico de publicações.")


_active_workers = set()


class UploadProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enviando para o YouTube")
        self.setMinimumWidth(490)
        self.setWindowModality(Qt.WindowModal)
        self.worker = None
        self.record = None
        self._done = False
        self.error_message = ""
        v = QVBoxLayout(self)
        v.setContentsMargins(T.SP5, T.SP4, T.SP5, T.SP4)
        v.setSpacing(T.SP3)
        v.addWidget(label("Envio do vídeo", "H2"))
        self.stage = label("Preparando envio…", "Dim", True)
        v.addWidget(self.stage)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        v.addWidget(self.bar)
        self.amount = label("0 B / 0 B", "Dim")
        v.addWidget(self.amount)
        row = QHBoxLayout()
        self.open_button = button("Abrir publicação", "open")
        self.open_button.setVisible(False)
        self.open_button.clicked.connect(self._open_publication)
        self.cancel_button = button("Cancelar envio", None, "Ghost")
        self.cancel_button.clicked.connect(self._cancel)
        self.close_button = button("Fechar", None, "Ghost")
        self.close_button.setVisible(False)
        self.close_button.clicked.connect(self.accept)
        row.addWidget(self.open_button)
        row.addStretch(1)
        row.addWidget(self.cancel_button)
        row.addWidget(self.close_button)
        v.addLayout(row)

    def start(self, service, request: PublishRequest):
        self.worker = UploadWorker(service, request)
        _active_workers.add(self.worker)
        self.worker.signals.progress.connect(self._progress)
        self.worker.signals.finished.connect(self._finished)
        QThreadPool.globalInstance().start(self.worker)
        self.exec()

    @staticmethod
    def _format_bytes(value: int) -> str:
        units = ("B", "KB", "MB", "GB")
        size = float(value)
        for unit in units:
            if size < 1024 or unit == units[-1]:
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024

    def _progress(self, sent: int, total: int, stage: str):
        self.stage.setText(stage)
        self.amount.setText(f"{self._format_bytes(sent)} / {self._format_bytes(total)}")
        self.bar.setValue(int(sent * 100 / total) if total else 0)

    def _finished(self, record, error):
        _active_workers.discard(self.worker)
        self._done = True
        self.worker = None
        self.cancel_button.hide()
        self.close_button.show()
        if error:
            self.error_message = error
            self.stage.setText(error)
            self.stage.setObjectName("Error")
            self.bar.setValue(0)
        else:
            self.record = record
            self.bar.setValue(100)
            status = record.get("status", "processing")
            text = {"scheduled": "Arquivo enviado e publicação agendada no YouTube.",
                    "published": "Vídeo publicado no YouTube.", "private": "Vídeo enviado como privado.",
                    "unlisted": "Vídeo enviado como não listado.",
                    "processing": "Arquivo enviado; o YouTube ainda está processando o vídeo."}.get(
                        status, "Arquivo enviado. Consulte o histórico para acompanhar o processamento.")
            self.stage.setText(text)
            self.amount.setText("Envio concluído")
            self.open_button.setVisible(bool(record.get("url")))

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self.stage.setText("Cancelando após a resposta atual do YouTube…")

    def _open_publication(self):
        if self.record and self.record.get("url"):
            QDesktopServices.openUrl(QUrl(self.record["url"]))

    def closeEvent(self, event):
        if not self._done and self.worker:
            self.worker.cancel()
            event.ignore()
            return
        super().closeEvent(event)
