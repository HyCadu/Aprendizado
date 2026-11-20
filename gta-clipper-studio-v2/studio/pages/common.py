from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import theme as T
from ..core import TWITCH, YOUTUBE
from ..storage import fmt_duration
from ..widgets import clip_thumb, rounded  # noqa: F401  (reexportados)

PLATFORM_LABEL = {YOUTUBE: "YouTube", TWITCH: "Live"}
PLATFORM_COLOR = {YOUTUBE: T.YOUTUBE_RED, TWITCH: T.TWITCH_PURPLE}
STATUS_COLOR = {"ok": T.SUCCESS, "erro": T.ERROR, "cancelado": T.WARNING, "pulado": T.MUTED, "pulada": T.MUTED,
                "rodando": T.INFO}
SYNC_INFO = {"ok": ("Legenda sincronizada", T.SUCCESS), "check": ("Sincronia: conferir", T.WARNING),
             "fail": ("Sincronia falhou", T.ERROR)}


class Page(QWidget):
    """Página com rolagem e conteúdo centralizado (largura máxima do design system)."""

    def __init__(self, scroll: bool = True, max_width: int = T.CONTENT_MAX_W, margins=None):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        body.setObjectName("Page")
        wrap = QVBoxLayout(body)
        m = margins or (T.SP8, T.SP6, T.SP8, T.SP8)
        wrap.setContentsMargins(*m)
        inner = QWidget()
        inner.setObjectName("Transparent")
        inner.setMaximumWidth(max_width)
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(T.SP6)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(inner, 100)
        row.addStretch(1)
        wrap.addLayout(row, 1)
        if scroll:
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # o conteúdo sempre cabe na largura
            sa.setWidget(body)
            sa.setFrameShape(QScrollArea.NoFrame)
            outer.addWidget(sa)
            self.scroll = sa
        else:
            outer.addWidget(body)
            self.scroll = None
        self.inner = inner

    def on_show(self):
        pass

    def on_hide(self):
        pass


def sync_info(clip):
    return SYNC_INFO.get(clip.sync_state)


def clip_meta(clip) -> tuple[str, str, str]:
    """(plataforma, data, duração) já formatados."""
    return PLATFORM_LABEL.get(clip.platform, ""), date_text(clip.mtime), fmt_duration(clip.duration)


def date_text(ts: float) -> str:
    if not ts:
        return ""
    d = int((time.time() - ts) // 86400)
    if d <= 0:
        return "hoje"
    if d == 1:
        return "ontem"
    if d < 7:
        return f"há {d} dias"
    return time.strftime("%d/%m/%Y", time.localtime(ts))


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
