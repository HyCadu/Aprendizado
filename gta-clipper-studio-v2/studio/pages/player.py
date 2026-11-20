"""Player vertical e controles acessíveis usados na visualização do clipe."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QFrame, QHBoxLayout, QSlider, QStackedLayout,
                               QSizePolicy, QVBoxLayout, QWidget)

from .. import theme as T
from ..widgets import EmptyState, button, glyph_icon, label, panel

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAS_MM = True
except ImportError:  # pragma: no cover
    HAS_MM = False


def _fmt_ms(ms: int) -> str:
    seconds = max(0, ms // 1000)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


class VerticalStage(QWidget):
    """Viewfinder 9:16; o vídeo dentro mantém a proporção original sem ser cortado."""

    def __init__(self, video=None, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoStage")
        self.video = video
        if video is not None:
            video.setParent(self)
            video.setAspectRatioMode(Qt.KeepAspectRatio)
            video.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.video is None:
            return
        width = self.width()
        height = self.height()
        # Mantém o quadro de visualização vertical e centralizado, limitado pelo espaço disponível.
        frame_width = min(width, round(height * 9 / 16))
        frame_height = min(height, round(width * 16 / 9))
        x = (width - frame_width) // 2
        y = (height - frame_height) // 2
        self.video.setGeometry(x, y, frame_width, frame_height)


class _FullscreenDialog(QDialog):
    def __init__(self, owner: "VideoPlayer"):
        super().__init__(owner, Qt.Window)
        self.owner = owner
        self.setObjectName("FullscreenPlayer")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(f"#FullscreenPlayer {{ background: #000; }}")
        self.setWindowTitle("Reprodução em tela cheia")
        self.video = QVideoWidget()
        self.stage = VerticalStage(self.video)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.stage, 1)
        owner.root_layout.removeWidget(owner.controls)
        owner.controls.setParent(self)
        layout.addWidget(owner.controls)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Space:
            self.owner.toggle()
        elif event.key() == Qt.Key_Left:
            self.owner.seek_relative(-5000)
        elif event.key() == Qt.Key_Right:
            self.owner.seek_relative(5000)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.owner._leave_fullscreen(self)
        super().closeEvent(event)


class VideoPlayer(QWidget):
    """Player vertical com busca, volume, velocidade, tela cheia e reprodução externa."""
    failed = Signal(str)
    external_requested = Signal(object)

    SPEEDS = [("0,5×", 0.5), ("0,75×", 0.75), ("1×", 1.0), ("1,25×", 1.25),
              ("1,5×", 1.5), ("2×", 2.0)]

    def __init__(self):
        super().__init__()
        self.setObjectName("VideoPlayer")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(T.SP3)

        self.screen = QFrame()
        self.screen.setObjectName("VideoScreen")
        # A altura do player acompanha a área disponível; o conteúdo permanece 9:16
        # dentro do palco e pode ser ampliado em tela cheia.
        self.screen.setMinimumHeight(320)
        self.screen.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.screen.setStyleSheet(
            f"#VideoScreen {{ background: #000; border: 1px solid {T.BORDER}; border-radius: {T.R_LG}px; }}"
            f"#VideoStage {{ background: #000; }}")
        self.screen_lay = QStackedLayout(self.screen)
        self.screen_lay.setContentsMargins(0, 0, 0, 0)
        self.error = EmptyState("video", "Não deu para tocar aqui", "Abra o arquivo no player do Windows.")
        self.video = None
        self.stage = None
        if HAS_MM:
            self.video = QVideoWidget()
            self.stage = VerticalStage(self.video)
            self.screen_lay.addWidget(self.stage)
        self.screen_lay.addWidget(self.error)
        self.root_layout.addWidget(self.screen, 1)

        self.controls = panel("Panel")
        self.controls.setObjectName("Panel")
        controls_layout = QVBoxLayout(self.controls)
        controls_layout.setContentsMargins(T.SP3, T.SP2, T.SP3, T.SP2)
        controls_layout.setSpacing(T.SP1)

        seek_row = QHBoxLayout()
        seek_row.setSpacing(T.SP2)
        self.b_play = button("", "play", "Ghost", "Reproduzir ou pausar (espaço)")
        self.b_play.clicked.connect(self.toggle)
        seek_row.addWidget(self.b_play)
        self.pos = QSlider(Qt.Horizontal)
        self.pos.setObjectName("PlayerSeek")
        self.pos.setRange(0, 0)
        self.pos.setToolTip("Arraste para mudar a posição do vídeo")
        seek_row.addWidget(self.pos, 1)
        self.current_time = label("0:00", "Mono")
        seek_row.addWidget(self.current_time)
        seek_row.addWidget(label("/", "Dim"))
        self.total_time = label("0:00", "Mono")
        seek_row.addWidget(self.total_time)
        self.b_fullscreen = button("", "fullscreen", "Ghost", "Abrir em tela cheia (Esc para sair)")
        self.b_fullscreen.clicked.connect(self.toggle_fullscreen)
        seek_row.addWidget(self.b_fullscreen)
        controls_layout.addLayout(seek_row)

        utility_row = QHBoxLayout()
        utility_row.setSpacing(T.SP2)
        self.b_mute = button("", "volume", "Ghost", "Silenciar áudio")
        self.b_mute.clicked.connect(self._mute)
        utility_row.addWidget(self.b_mute)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setObjectName("PlayerVolume")
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.setFixedWidth(92)
        self.volume.setToolTip("Volume")
        utility_row.addWidget(self.volume)
        utility_row.addSpacing(T.SP2)
        utility_row.addWidget(label("Velocidade", "Dim"))
        self.speed = QComboBox()
        self.speed.setObjectName("PlayerSpeed")
        self.speed.setFixedWidth(82)
        for text, value in self.SPEEDS:
            self.speed.addItem(text, value)
        self.speed.setCurrentIndex(2)
        utility_row.addWidget(self.speed)
        utility_row.addStretch(1)
        self.b_external = button("Abrir no Windows", "open", "Ghost", "Reproduzir no player externo")
        self.b_external.clicked.connect(self._open_external)
        utility_row.addWidget(self.b_external)
        controls_layout.addLayout(utility_row)
        self.root_layout.addWidget(self.controls)

        self.player = None
        self.audio = None
        self._fullscreen_dialog = None
        self._path: Path | None = None
        if HAS_MM:
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.audio.setVolume(0.8)
            self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.player.durationChanged.connect(self._duration_changed)
            self.player.positionChanged.connect(self._position_changed)
            self.player.playbackStateChanged.connect(self._state_changed)
            self.player.errorOccurred.connect(self._error)
            self.pos.sliderMoved.connect(self.player.setPosition)
            self.volume.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))
            self.speed.currentIndexChanged.connect(self._speed_changed)
        else:
            self.screen_lay.setCurrentWidget(self.error)
            for widget in (self.b_play, self.pos, self.b_mute, self.volume, self.speed, self.b_fullscreen):
                widget.setEnabled(False)

    def load(self, path: Path, autoplay: bool = True):
        self._path = Path(path)
        if not self.player:
            return
        self.screen_lay.setCurrentWidget(self.stage)
        self.player.setSource(QUrl.fromLocalFile(str(self._path)))
        self._speed_changed(self.speed.currentIndex())
        if autoplay:
            self.player.play()

    def stop(self):
        if self._fullscreen_dialog:
            self._fullscreen_dialog.close()
        if self.player:
            self.player.stop()
            self.player.setSource(QUrl())
            self.pos.setValue(0)
            self.current_time.setText("0:00")
            self.total_time.setText("0:00")

    def toggle(self):
        if not self.player:
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def seek_relative(self, delta_ms: int):
        if self.player:
            target = max(0, min(self.player.duration(), self.player.position() + delta_ms))
            self.player.setPosition(target)

    def _mute(self):
        if not self.audio:
            return
        muted = not self.audio.isMuted()
        self.audio.setMuted(muted)
        self.b_mute.setIcon(glyph_icon("mute" if muted else "volume", T.MUTED, 14))
        self.b_mute.setToolTip("Ativar áudio" if muted else "Silenciar áudio")

    def _duration_changed(self, duration: int):
        self.pos.setRange(0, max(0, duration))
        self.total_time.setText(_fmt_ms(duration))

    def _position_changed(self, position: int):
        if not self.pos.isSliderDown():
            self.pos.setValue(position)
        self.current_time.setText(_fmt_ms(position))

    def _speed_changed(self, index: int):
        if self.player and index >= 0:
            self.player.setPlaybackRate(float(self.speed.itemData(index)))

    def _state_changed(self, state):
        playing = state == QMediaPlayer.PlayingState
        self.b_play.setIcon(glyph_icon("pause" if playing else "play", T.MUTED, 14))
        self.b_play.setToolTip("Pausar vídeo (espaço)" if playing else "Reproduzir vídeo (espaço)")

    def _error(self, *_):
        if self._fullscreen_dialog:
            self._fullscreen_dialog.close()
        self.screen_lay.setCurrentWidget(self.error)
        self.failed.emit(self.player.errorString())

    def _open_external(self):
        if self._path:
            if self.player:
                self.player.pause()
            self.external_requested.emit(self._path)

    def toggle_fullscreen(self):
        if not self.player or not self.video:
            return
        if self._fullscreen_dialog:
            self._fullscreen_dialog.close()
            return
        dialog = _FullscreenDialog(self)
        self._fullscreen_dialog = dialog
        self.player.setVideoOutput(dialog.video)
        self.b_fullscreen.setToolTip("Sair da tela cheia (Esc)")
        dialog.showFullScreen()

    def _leave_fullscreen(self, dialog):
        if self._fullscreen_dialog is not dialog:
            return
        dialog.layout().removeWidget(self.controls)
        self.controls.setParent(self)
        self.root_layout.addWidget(self.controls)
        if self.player and self.video:
            self.player.setVideoOutput(self.video)
        self._fullscreen_dialog = None
        self.b_fullscreen.setToolTip("Abrir em tela cheia (Esc para sair)")
