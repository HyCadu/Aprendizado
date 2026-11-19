from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from .. import theme as T
from ..core import TWITCH, YOUTUBE
from ..storage import fmt_duration, fmt_size
from ..widgets import FlowLayout, Icon, badge, icon_button, label
from .common import PLATFORM_COLOR, PLATFORM_LABEL, Page, clip_thumb, open_file, open_folder, rounded

CARD_W = 210


class ClipCard(QFrame):
    def __init__(self, clip, state):
        super().__init__()
        self.clip = clip
        self.setObjectName("Card")
        self.setFixedWidth(CARD_W)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 12)
        v.setSpacing(8)
        tw = CARD_W - 20
        img = QLabel()
        img.setFixedSize(tw, int(tw * 16 / 9))
        img.setPixmap(rounded(clip_thumb(clip.sheet, tw, clip.mtime), 10))
        img.setCursor(Qt.PointingHandCursor)
        img.setToolTip("Assistir")
        img.mousePressEvent = lambda _e: state.play_clip.emit(clip)
        # selos sobre a miniatura
        ov = QHBoxLayout(img)
        ov.setContentsMargins(8, 8, 8, 8)
        top = QVBoxLayout()
        row = QHBoxLayout()
        if clip.score is not None:
            row.addWidget(badge(f"★ {clip.score:.1f}", T.AMBER))
        row.addStretch(1)
        row.addWidget(badge(fmt_duration(clip.duration), T.TEXT))
        top.addLayout(row)
        top.addStretch(1)
        play = Icon("play", 22, "#ffffff")
        play.setFixedSize(52, 52)
        play.setStyleSheet("color: white; background: rgba(0,0,0,0.45); border-radius: 26px;")
        top.addWidget(play, 0, Qt.AlignCenter)
        top.addStretch(1)
        ov.addLayout(top)
        v.addWidget(img)

        t = label(clip.title, wrap=True)
        t.setStyleSheet("font-weight: 700; font-size: 12px;")
        t.setFixedHeight(34)
        t.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        t.setToolTip(clip.title)
        v.addWidget(t)
        fn = label(clip.name, "Dim")
        fn.setToolTip(str(clip.path))
        fn.setText(fn.fontMetrics().elidedText(clip.name, Qt.ElideMiddle, tw))
        v.addWidget(fn)
        b = QHBoxLayout()
        b.setSpacing(6)
        b.addWidget(badge(PLATFORM_LABEL.get(clip.platform, ""), PLATFORM_COLOR.get(clip.platform, T.MUTED)))
        ss = clip.sync_state
        if ss:
            b.addWidget(badge({"ok": "SYNC OK", "fail": "SYNC FAIL", "check": "SYNC ?"}[ss],
                              {"ok": T.GREEN, "fail": T.RED, "check": T.AMBER}[ss]))
        b.addStretch(1)
        v.addLayout(b)
        acts = QHBoxLayout()
        acts.setSpacing(6)
        p = icon_button("Assistir", "play", "Ghost")
        p.clicked.connect(lambda: state.play_clip.emit(clip))
        f = icon_button("", "folder", "Ghost", "Abrir pasta do clipe")
        f.setFixedWidth(40)
        f.clicked.connect(lambda: open_folder(clip.path, select=True))
        d = icon_button("", "doc", "Ghost", "Abrir post.md (título, descrição e hashtags)")
        d.setFixedWidth(40)
        d.clicked.connect(lambda: open_file(clip.post_md))
        d.setEnabled(clip.post_md.exists())
        acts.addWidget(p, 1)
        acts.addWidget(f)
        acts.addWidget(d)
        v.addLayout(acts)
        self.setToolTip(f"{clip.video_title}\n{clip.channel}\n{fmt_size(clip.size)} · "
                        f"{time.strftime('%d/%m/%Y %H:%M', time.localtime(clip.mtime))}")


class Library(Page):
    def __init__(self, state):
        super().__init__("Biblioteca", "Todos os vídeos gerados pelas skills")
        self.state = state
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por título, canal ou arquivo…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(220)
        self.search.setMaximumWidth(300)
        self.search.textChanged.connect(lambda: self._debounce.start(180))
        self.head_right.addWidget(self.search, 1)
        r = icon_button("", "refresh", "Ghost", "Atualizar")
        r.setFixedWidth(42)
        r.clicked.connect(state.refresh_clips)
        self.head_right.addWidget(r)

        bar_w = QWidget()
        bar = FlowLayout(bar_w, 8)
        self.fgroup = QButtonGroup(self)
        for i, (key, txt) in enumerate((("all", "Todos"), (YOUTUBE, "YouTube"), (TWITCH, "Lives (Twitch)"))):
            b = QPushButton(txt)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("key", key)
            if i == 0:
                b.setChecked(True)
            self.fgroup.addButton(b, i)
            bar.addWidget(b)
        self.fgroup.idClicked.connect(lambda _i: self._render())
        self.count = label("", "Muted")
        self.count.setMinimumHeight(38)
        bar.addWidget(self.count)
        oy = icon_button("Pasta YouTube", "folder", "Ghost")
        oy.clicked.connect(lambda: open_folder(state.settings.out_dir(YOUTUBE)))
        ot = icon_button("Pasta Lives", "folder", "Ghost")
        ot.clicked.connect(lambda: open_folder(state.settings.out_dir(TWITCH)))
        bar.addWidget(oy)
        bar.addWidget(ot)
        self.body.addWidget(bar_w)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(16)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        # nº de colunas vem da largura (resizeEvent); a grade nunca força rolagem horizontal
        self.grid_host.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.body.addWidget(self.grid_host)
        self.body.addStretch(1)
        self._cols = 0
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._render)
        state.clips_changed.connect(self._render)

    def on_show(self):
        self.state.refresh_clips()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = max(1, (self.content_width() + 16) // (CARD_W + 16))
        if cols != self._cols:
            self._cols = cols
            self._debounce.start(60)

    def _filtered(self):
        key = self.fgroup.checkedButton().property("key")
        q = self.search.text().strip().lower()
        out = []
        for c in self.state.clips:
            if key != "all" and c.platform != key:
                continue
            if q and q not in f"{c.title} {c.name} {c.channel} {c.video_title} {c.hook}".lower():
                continue
            out.append(c)
        return out

    def _render(self):
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        clips = self._filtered()
        total = len(self.state.clips)
        self.count.setText(f"{len(clips)} de {total} clipe(s)")
        if not clips:
            msg = ("Nenhum clipe encontrado com esse filtro." if total else
                   "Nenhum clipe ainda. Os vídeos gerados aparecem aqui automaticamente.")
            e = label(msg, "Muted", wrap=True)
            self.grid.addWidget(e, 0, 0)
            return
        cols = max(1, self._cols or 4)
        for i, c in enumerate(clips[:400]):
            self.grid.addWidget(ClipCard(c, self.state), i // cols, i % cols)
