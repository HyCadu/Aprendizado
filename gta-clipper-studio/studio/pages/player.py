"""Player embutido (QtMultimedia) com o texto do post ao lado."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QHBoxLayout, QSlider, QTextBrowser, QVBoxLayout

from .. import theme as T
from ..storage import fmt_duration, fmt_size
from ..widgets import badge, icon_button, label
from .common import open_file, open_folder

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAS_MM = True
except ImportError:  # pragma: no cover
    HAS_MM = False


def _fmt_ms(ms: int) -> str:
    s = max(0, ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


class PlayerDialog(QDialog):
    def __init__(self, clip, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.setWindowTitle(f"{clip.title} — GTA CLIPPER STUDIO")
        self.resize(1040, 760)
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 18, 18, 18)
        h.setSpacing(18)

        left = QVBoxLayout()
        self.video = QVideoWidget()
        self.video.setMinimumSize(380, 600)
        self.video.setStyleSheet("background: black; border-radius: 12px;")
        left.addWidget(self.video, 1)
        ctr = QHBoxLayout()
        self.b_play = icon_button("", "pause", "Ghost", "Play / pausa (espaço)")
        self.b_play.setFixedWidth(44)
        self.b_play.clicked.connect(self.toggle)
        ctr.addWidget(self.b_play)
        self.pos = QSlider(Qt.Horizontal)
        self.pos.sliderMoved.connect(lambda v: self.player.setPosition(v))
        ctr.addWidget(self.pos, 1)
        self.t = label("0:00 / 0:00", "Muted")
        ctr.addWidget(self.t)
        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(80)
        self.vol.setFixedWidth(90)
        ctr.addWidget(self.vol)
        left.addLayout(ctr)
        h.addLayout(left, 5)

        right = QVBoxLayout()
        right.setSpacing(10)
        tl = label(clip.title, wrap=True)
        tl.setStyleSheet("font-size: 18px; font-weight: 800;")
        right.addWidget(tl)
        meta = QHBoxLayout()
        if clip.score is not None:
            meta.addWidget(badge(f"★ {clip.score:.1f}", T.AMBER))
        meta.addWidget(badge(fmt_duration(clip.duration), T.TEXT))
        meta.addWidget(badge(fmt_size(clip.size), T.MUTED))
        meta.addStretch(1)
        right.addLayout(meta)
        if clip.hook:
            right.addWidget(label(f"Hook: {clip.hook}", "Muted", wrap=True))
        if clip.channel or clip.video_title:
            right.addWidget(label(f"{clip.channel} · {clip.video_title}", "Dim", wrap=True))
        if clip.sync:
            col = {"ok": T.GREEN, "fail": T.RED}.get(clip.sync_state, T.AMBER)
            s = label(clip.sync, wrap=True)
            s.setStyleSheet(f"color: {col}; font-size: 12px;")
            right.addWidget(s)
        fn = label(str(clip.path), "Dim", wrap=True)
        fn.setTextInteractionFlags(Qt.TextSelectableByMouse)
        right.addWidget(fn)
        right.addWidget(label("Texto do post", "SectionTitle"))
        self.post = QTextBrowser()
        self.post.setObjectName("Post")
        try:
            self.post.setPlainText(clip.post_md.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            self.post.setPlainText("post.md não encontrado.")
        right.addWidget(self.post, 1)
        acts = QHBoxLayout()
        cp = icon_button("Copiar post", "copy", "Ghost")
        cp.clicked.connect(self._copy_post)
        fo = icon_button("Pasta", "folder", "Ghost")
        fo.clicked.connect(lambda: open_folder(clip.path, select=True))
        ex = icon_button("Player do Windows", "open", "Ghost")
        ex.clicked.connect(lambda: open_file(clip.path))
        for b in (cp, fo, ex):
            acts.addWidget(b)
        right.addLayout(acts)
        right.addWidget(label("Assista antes de postar. Só publique cortes de quem permite, com crédito.",
                              "Dim", wrap=True))
        h.addLayout(right, 4)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.8)
        self.vol.valueChanged.connect(lambda v: self.audio.setVolume(v / 100))
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.durationChanged.connect(lambda d: self.pos.setRange(0, d))
        self.player.positionChanged.connect(self._pos)
        self.player.playbackStateChanged.connect(self._state)
        self.player.errorOccurred.connect(self._error)
        self.player.setSource(QUrl.fromLocalFile(str(clip.path)))
        self.player.play()

    def _pos(self, p):
        if not self.pos.isSliderDown():
            self.pos.setValue(p)
        self.t.setText(f"{_fmt_ms(p)} / {_fmt_ms(self.player.duration())}")

    def _state(self, st):
        playing = st == QMediaPlayer.PlayingState
        self.b_play._icon.setText("" if playing else "")

    def _error(self, *_):
        self.post.append(f"\n\n⚠ Não deu para tocar aqui ({self.player.errorString()}). "
                         "Use o botão 'Player do Windows'.")

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Space:
            self.toggle()
        else:
            super().keyPressEvent(e)

    def _copy_post(self):
        QGuiApplication.clipboard().setText(self.post.toPlainText())

    def closeEvent(self, e):
        self.player.stop()
        super().closeEvent(e)

    def done(self, r):
        self.player.stop()
        super().done(r)


def play(clip, parent=None):
    if not HAS_MM:
        open_file(clip.path)
        return
    dlg = PlayerDialog(clip, parent)
    dlg.setAttribute(Qt.WA_DeleteOnClose)
    dlg.show()
