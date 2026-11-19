from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import theme as T
from ..core import TWITCH, YOUTUBE
from ..storage import SHEET_CELL
from ..widgets import AdaptiveBox, label

PLATFORM_LABEL = {YOUTUBE: "YouTube", TWITCH: "Lives"}
PLATFORM_COLOR = {YOUTUBE: "#ff4e45", TWITCH: T.PURPLE}
STATUS_COLOR = {"ok": T.GREEN, "erro": T.RED, "cancelado": T.AMBER, "pulado": T.MUTED, "pulada": T.MUTED,
                "rodando": T.CYAN}


class Page(QWidget):
    """Página com título, subtítulo e área de rolagem. Responsiva: margens menores e cabeçalho em duas
    linhas quando a janela fica estreita."""

    NARROW = 760  # abaixo disso (largura da página) as margens encolhem

    def __init__(self, title: str, subtitle: str, scroll: bool = True):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        body.setObjectName("Page")
        self.body = QVBoxLayout(body)
        self.margin = 36
        self.body.setContentsMargins(36, 30, 36, 30)
        self.body.setSpacing(18)
        head = AdaptiveBox(620, 10)
        tw = QWidget()
        tv = QVBoxLayout(tw)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(2)
        tv.addWidget(label(title, "PageTitle"))
        self.subtitle = label(subtitle, "PageSub", wrap=True)
        tv.addWidget(self.subtitle)
        head.box.addWidget(tw, 1)
        hr = QWidget()
        self.head_right = QHBoxLayout(hr)
        self.head_right.setContentsMargins(0, 0, 0, 0)
        self.head_right.setSpacing(8)
        head.box.addWidget(hr, 0)
        # janela estreita: título em cima e os botões do cabeçalho embaixo, alinhados à esquerda
        head.on_change = lambda v: head.box.setAlignment(hr, Qt.AlignLeft if v else Qt.Alignment(0))
        self.body.addWidget(head)
        if scroll:
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setWidget(body)
            sa.setFrameShape(QScrollArea.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            outer.addWidget(sa)
        else:
            outer.addWidget(body)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        m = 36 if e.size().width() >= self.NARROW else 16
        if m != self.margin:
            self.margin = m
            self.body.setContentsMargins(m, 30 if m == 36 else 18, m, 30 if m == 36 else 18)

    def content_width(self) -> int:
        """Largura útil dentro das margens (descontando a barra de rolagem)."""
        return self.width() - 2 * self.margin - 12

    def on_show(self):
        pass


_thumb_cache: dict[tuple[str, float, int], QPixmap] = {}


def clip_thumb(sheet: Path, width: int, mtime: float = 0.0) -> QPixmap:
    """Primeiro quadro do sheet.jpg (grade 6x2 de 270x480) em 9:16."""
    key = (str(sheet), mtime, width)
    if key in _thumb_cache:
        return _thumb_cache[key]
    h = int(width * 16 / 9)
    pm = QPixmap(str(sheet)) if sheet.is_file() else QPixmap()
    if not pm.isNull():
        x, y, w, hh = SHEET_CELL
        pm = pm.copy(x, y, w, hh).scaled(width, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    else:
        pm = QPixmap(width, h)
        pm.fill(QColor(T.SURFACE_2))
        p = QPainter(pm)
        p.setPen(QColor(T.DIM))
        p.drawText(pm.rect(), Qt.AlignCenter, "sem prévia")
        p.end()
    _thumb_cache[key] = pm
    return pm


def rounded(pm: QPixmap, radius: int = 12) -> QPixmap:
    out = QPixmap(pm.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(pm)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(out.rect(), radius, radius)
    p.end()
    return out


def open_folder(path: Path, select: bool = False):
    """Abre no Explorer (com o arquivo selecionado, se pedir). Só abre: não move nem apaga nada."""
    path = Path(path)
    if os.name != "nt":
        return
    if select and path.exists():
        subprocess.Popen(["explorer", "/select,", str(path)])
    else:
        target = path if path.is_dir() else path.parent
        if target.exists():
            os.startfile(str(target))  # noqa: S606


def open_file(path: Path):
    if Path(path).exists() and os.name == "nt":
        os.startfile(str(path))  # noqa: S606
