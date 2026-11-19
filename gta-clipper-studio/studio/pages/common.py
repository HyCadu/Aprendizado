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
from ..widgets import label

PLATFORM_LABEL = {YOUTUBE: "YouTube", TWITCH: "Lives"}
PLATFORM_COLOR = {YOUTUBE: "#ff4e45", TWITCH: T.PURPLE}
STATUS_COLOR = {"ok": T.GREEN, "erro": T.RED, "cancelado": T.AMBER, "pulado": T.MUTED, "pulada": T.MUTED,
                "rodando": T.CYAN}


class Page(QWidget):
    """Página com título, subtítulo e área de rolagem."""

    def __init__(self, title: str, subtitle: str, scroll: bool = True):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        body.setObjectName("Page")
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(36, 30, 36, 30)
        self.body.setSpacing(18)
        head = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(label(title, "PageTitle"))
        self.subtitle = label(subtitle, "PageSub")
        tv.addWidget(self.subtitle)
        head.addLayout(tv, 1)
        self.head_right = QHBoxLayout()
        self.head_right.setSpacing(8)
        head.addLayout(self.head_right)
        self.body.addLayout(head)
        if scroll:
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setWidget(body)
            sa.setFrameShape(QScrollArea.NoFrame)
            outer.addWidget(sa)
        else:
            outer.addWidget(body)

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
