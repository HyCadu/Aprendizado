"""Biblioteca: galeria de clipes (grade ou lista) com busca, filtros e visualização com player."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
                               QScrollArea, QStackedWidget, QSizePolicy, QVBoxLayout, QWidget)

from .. import theme as T
from ..core import LEGENDAS, TWITCH, YOUTUBE
from ..dialogs.publish_video import PublishVideoDialog, UploadProgressDialog
from ..storage import fmt_duration, fmt_size
from ..widgets import (Badge, EmptyState, Segmented, Select, StatusDot, Thumb, VideoCard, button, clear_layout,
                       divider, elide, glyph_icon, label)
from .common import PLATFORM_COLOR, PLATFORM_LABEL, Page, clip_meta, open_file, open_folder, sync_info
from .player import VideoPlayer

CARD_W = 172
DAY = 86400


def _ts(sec) -> str:
    if sec is None:
        return "--"
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


class ListRow(QFrame):
    """Linha da visualização em lista."""

    def __init__(self, clip, on_open):
        super().__init__()
        self.setObjectName("ListRow")
        self.setCursor(Qt.PointingHandCursor)
        self.mouseReleaseEvent = lambda e: on_open(clip) if e.button() == Qt.LeftButton else None
        h = QHBoxLayout(self)
        h.setContentsMargins(T.SP2, T.SP2, T.SP3, T.SP2)
        h.setSpacing(T.SP3)
        th = Thumb(clip.sheet, 40, clip.mtime)
        th.clicked.connect(lambda: on_open(clip))
        h.addWidget(th)
        v = QVBoxLayout()
        v.setSpacing(2)
        t = label("", "H3")
        elide(t, clip.title, 460)
        v.addWidget(t)
        s = label("", "Dim")
        elide(s, " · ".join(x for x in (clip.channel, clip.video_title) if x), 460)
        v.addWidget(s)
        h.addLayout(v, 1)
        plat, date, dur = clip_meta(clip)
        h.addWidget(Badge(plat, PLATFORM_COLOR.get(clip.platform, T.MUTED)))
        for txt, w in ((f"{clip.score:.1f}" if clip.score is not None else "", 40), (dur, 48), (date, 84)):
            lb = label(txt, "Dim")
            lb.setFixedWidth(w)
            lb.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(lb)
        si = sync_info(clip)
        d = StatusDot(si[1] if si else T.BORDER, 6)
        d.setToolTip(si[0] if si else "Sem verificação de sincronia")
        h.addWidget(d)


class ClipDetail(QWidget):
    """Visualização individual: player à esquerda, detalhes à direita."""

    def __init__(self, state, on_back):
        super().__init__()
        self.state = state
        self.clip = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(T.SP3)
        back = button("Voltar para biblioteca", "back", "Ghost")
        back.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        back.clicked.connect(on_back)
        v.addWidget(back)
        h = QHBoxLayout()
        h.setSpacing(T.SP6)
        self.player = VideoPlayer()
        self.player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.player.external_requested.connect(open_file)
        h.addWidget(self.player, 65)

        right = QWidget()
        rv = QVBoxLayout(right)
        right.setMinimumWidth(0)
        rv.setContentsMargins(T.SP4, T.SP2, T.SP2, T.SP2)
        rv.setSpacing(T.SP3)
        rv.addWidget(label("DETALHES DO CLIPE", "Label"))
        self.title = label("", "H1", wrap=True)
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rv.addWidget(self.title)
        self.chips = QGridLayout()
        self.chips.setHorizontalSpacing(T.SP2)
        self.chips.setVerticalSpacing(T.SP2)
        self.chips.setContentsMargins(0, 0, 0, 0)
        rv.addLayout(self.chips)
        self.hook = label("", "Muted", wrap=True)
        self.hook.setObjectName("ClipHook")
        self.hook.setStyleSheet(
            f"#ClipHook {{ background: {T.ELEVATED}; border: 1px solid {T.BORDER}; "
            f"border-radius: {T.R_MD}px; padding: {T.SP2}px; }}")
        rv.addWidget(self.hook)

        rv.addWidget(divider())
        self.pub = button("Publicar", "upload", "Primary",
                          "Escolha uma plataforma para publicar este clipe.")
        self.pub.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.publish_menu = QMenu(self.pub)
        self.youtube_action = self.publish_menu.addAction("YouTube Shorts")
        self.youtube_action.triggered.connect(lambda _checked=False: self._publish_clip())
        self.publish_menu.addSeparator()
        for platform in ("Instagram Reels", "TikTok", "Facebook Reels"):
            action = self.publish_menu.addAction(f"{platform} — em breve")
            action.setEnabled(False)
        self.pub.setMenu(self.publish_menu)
        self.state.youtube_changed.connect(self._youtube_status_changed)
        rv.addWidget(self.pub)
        self.publish_hint = label("", "Dim", wrap=True)
        rv.addWidget(self.publish_hint)

        acts = QHBoxLayout()
        acts.setSpacing(T.SP2)
        cp = button("Copiar texto", "copy", "Primary")
        cp.clicked.connect(self._copy_post)
        fo = button("Abrir pasta", "folder")
        fo.clicked.connect(lambda: self.clip and open_folder(self.clip.path, select=True))
        acts.addWidget(cp, 1)
        acts.addWidget(fo)
        rv.addLayout(acts)
        rv.addWidget(divider())

        self.fields = QVBoxLayout()
        self.fields.setContentsMargins(0, 0, 0, 0)
        self.fields.setSpacing(T.SP3)
        rv.addLayout(self.fields)
        rv.addWidget(label("Publique apenas cortes que você tem permissão para compartilhar.", "Dim", wrap=True))
        rv.addStretch(1)

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setMinimumWidth(0)
        sa.setFrameShape(QScrollArea.NoFrame)
        sa.setWidget(right)
        h.addWidget(sa, 35)
        v.addLayout(h, 1)

    def show_clip(self, clip):
        self.clip = clip
        self._youtube_status_changed()
        self.title.setText(clip.title)
        self.hook.setText(f"Hook: {clip.hook}" if clip.hook else "")
        self.hook.setVisible(bool(clip.hook))
        clear_layout(self.chips)
        plat, date, dur = clip_meta(clip)
        badges = [Badge(plat, PLATFORM_COLOR.get(clip.platform, T.MUTED)), Badge(dur, T.MUTED)]
        if clip.score is not None:
            badges.append(Badge(f"Nota {clip.score:.1f}", T.SECONDARY))
        si = sync_info(clip)
        if si:
            badges.append(Badge(si[0], si[1]))
        if clip.language in LEGENDAS:
            badges.append(Badge(f"Legenda {LEGENDAS[clip.language]}", T.MUTED))
        for i, item in enumerate(badges):
            self.chips.addWidget(item, i // 2, i % 2, Qt.AlignLeft)

        clear_layout(self.fields)
        rows = [
            ("Descrição", clip.caption or "—"),
            ("Hashtags", " ".join(clip.hashtags) if clip.hashtags else "—"),
            ("Vídeo original", " · ".join(x for x in (clip.channel, clip.video_title) if x) or "—"),
            ("Trecho", f"{_ts(clip.start)} – {_ts(clip.end)}" if clip.start is not None else "—"),
            ("Link original", clip.source or "—"),
            ("Sincronização", clip.sync or "Não verificada"),
            ("Arquivo", f"{clip.path}  ·  {fmt_size(clip.size)}"),
            ("Gerado em", time.strftime("%d/%m/%Y %H:%M", time.localtime(clip.mtime))),
        ]
        for i, (k, val) in enumerate(rows):
            block = QWidget()
            block.setObjectName("Transparent")
            bv = QVBoxLayout(block)
            bv.setContentsMargins(0, 0, 0, 0)
            bv.setSpacing(T.SP1)
            kl = label(k, "Label")
            vl = label(val, wrap=True)
            vl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if k in ("Arquivo", "Link original"):
                vl.setObjectName("Dim")
            bv.addWidget(kl)
            bv.addWidget(vl)
            self.fields.addWidget(block)
            if i < len(rows) - 1:
                self.fields.addWidget(divider())
        self.player.load(clip.path)

    def _youtube_status_changed(self):
        connected = self.state.youtube_status == "connected" and self.state.youtube_account is not None
        # O menu permanece acessível quando desconectado para que YouTube Shorts
        # possa encaminhar o usuário à tela Integrações e solicitar a conexão.
        self.pub.setEnabled(True)
        self.youtube_action.setEnabled(True)
        if connected:
            title = self.state.youtube_account.get("title", "")
            self.pub.setToolTip(f"Publicar no canal {title}")
            self.publish_hint.setText(f"Destino: {title}" if title else "Conta YouTube conectada.")
        else:
            self.pub.setToolTip("Conecte uma conta YouTube na página Integrações para publicar.")
            self.publish_hint.setText("Conecte sua conta do YouTube em Integrações para habilitar o envio.")

    def _publish_clip(self):
        if not self.clip:
            return
        if self.state.youtube_status != "connected" or not self.state.youtube_account:
            QMessageBox.information(self, "YouTube desconectado", "Conecte sua conta na página Integrações antes de publicar.")
            self.state.navigate.emit("integrations")
            return
        if not self.state.publication_service:
            QMessageBox.warning(self, "Integração indisponível", "As bibliotecas oficiais de publicação não estão disponíveis.")
            return
        review = PublishVideoDialog(self.clip, self.state.youtube_account, self)
        if review.exec() != QDialog.Accepted or not review.request:
            return
        progress = UploadProgressDialog(self)
        progress.start(self.state.publication_service, review.request)
        self.state.refresh_publications(reconcile=True)
        if progress.record:
            self.state.toast.emit("Envio concluído. Consulte o histórico para acompanhar o processamento do YouTube.", "info")
        elif progress._done:
            self.state.toast.emit(progress.error_message or "O envio não foi concluído. Confira o histórico de publicações.", "error")
            self.state.refresh_youtube()

    def _copy_post(self):
        if not self.clip:
            return
        try:
            text = self.clip.post_md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = "\n\n".join(x for x in (self.clip.title, self.clip.caption, " ".join(self.clip.hashtags)) if x)
        QGuiApplication.clipboard().setText(text)
        self.state.toast.emit("Texto da publicação copiado.", "info")

    def stop(self):
        self.player.stop()


class Library(Page):
    def __init__(self, state):
        # A galeria rola dentro da própria aba; o detalhe ocupa a altura disponível
        # da janela sem herdar a rolagem da lista de clipes.
        super().__init__(scroll=False)
        self.state = state
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack)

        # ------------------------------------------------ galeria
        gal = QWidget()
        gv = QVBoxLayout(gal)
        gv.setContentsMargins(0, 0, 0, 0)
        gv.setSpacing(T.SP4)
        head = QHBoxLayout()
        head.setSpacing(T.SP2)
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(label("Biblioteca", "H1"))
        self.count = label("", "Dim")
        tv.addWidget(self.count)
        head.addLayout(tv, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por título ou canal")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(glyph_icon("search", T.DIM, 13), QLineEdit.LeadingPosition)
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(lambda: self._debounce.start(160))
        head.addWidget(self.search)
        self.view = Segmented([("grid", "grid"), ("list", "list")], icons=True)
        self.view.set_value(state.settings["library_view"])
        self.view.changed.connect(self._on_view)
        head.addWidget(self.view)
        folders = button("", "folder", "Ghost", "Abrir pasta dos clipes")
        menu = QMenu(folders)
        for txt, plat in (("Pasta dos vídeos do YouTube", YOUTUBE), ("Pasta das lives", TWITCH)):
            a = QAction(txt, menu)
            a.triggered.connect(lambda _c=False, p=plat: open_folder(state.settings.out_dir(p)))
            menu.addAction(a)
        folders.clicked.connect(lambda: menu.exec(folders.mapToGlobal(folders.rect().bottomLeft())))
        head.addWidget(folders)
        rf = button("", "refresh", "Ghost", "Atualizar")
        rf.clicked.connect(state.refresh_clips)
        head.addWidget(rf)
        gv.addLayout(head)

        filters = QHBoxLayout()
        filters.setSpacing(T.SP2)
        self.f_plat = Select([("all", "Todas as origens"), (YOUTUBE, "YouTube"), (TWITCH, "Lives")])
        self.f_date = Select([("all", "Qualquer data"), (1, "Hoje"), (7, "Últimos 7 dias"), (30, "Últimos 30 dias")])
        self.f_sync = Select([("all", "Qualquer sincronia"), ("ok", "Sincronizada"), ("check", "A conferir"),
                              ("fail", "Falhou"), ("", "Sem verificação")])
        self.f_sort = Select([("recent", "Mais recentes"), ("old", "Mais antigos"), ("long", "Maior duração"),
                              ("short", "Menor duração"), ("score", "Maior nota")])
        self.f_sort.set_key(state.settings["library_sort"])
        for s in (self.f_plat, self.f_date, self.f_sync, self.f_sort):
            s.setMinimumWidth(150)
            s.currentIndexChanged.connect(lambda _i: self._debounce.start(10))
            filters.addWidget(s)
        filters.addStretch(1)
        self.clear_f = button("Limpar filtros", None, "Ghost")
        self.clear_f.clicked.connect(self._clear_filters)
        filters.addWidget(self.clear_f)
        gv.addLayout(filters)

        self.content = QStackedWidget()
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(T.SP5)
        self.grid.setVerticalSpacing(T.SP6)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.list_host = QWidget()
        self.list = QVBoxLayout(self.list_host)
        self.list.setContentsMargins(0, 0, 0, 0)
        self.list.setSpacing(2)
        self.list.setAlignment(Qt.AlignTop)
        go = button("Criar cortes", "add", "Primary")
        go.clicked.connect(lambda: state.navigate.emit("create"))
        self.empty_lib = EmptyState("library", "Biblioteca vazia", "Os clipes gerados aparecem aqui sozinhos.", go)
        clr = button("Limpar filtros", None)
        clr.clicked.connect(self._clear_filters)
        self.empty_res = EmptyState("search", "Nenhum resultado", "Nenhum clipe com esses filtros.", clr)
        for w in (self.grid_host, self.list_host, self.empty_lib, self.empty_res):
            self.content.addWidget(w)
        gv.addWidget(self.content)
        gv.addStretch(1)
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.gallery_scroll.setFrameShape(QScrollArea.NoFrame)
        self.gallery_scroll.setWidget(gal)
        self.stack.addWidget(self.gallery_scroll)

        # ------------------------------------------------ detalhe
        self.detail = ClipDetail(state, self.back)
        self.stack.addWidget(self.detail)
        self._library_scroll_pos = 0

        self._cols = 0
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._render)
        state.clips_changed.connect(self._render)

    # ------------------------------------------------------------
    def on_show(self):
        self.state.refresh_clips()

    def on_hide(self):
        self.detail.stop()

    def open_clip(self, clip):
        if self.stack.currentIndex() == 0:
            self._library_scroll_pos = self.gallery_scroll.verticalScrollBar().value()
        self.stack.setCurrentIndex(1)
        self.detail.show_clip(clip)

    def back(self):
        self.detail.stop()
        self.stack.setCurrentIndex(0)
        QTimer.singleShot(0, lambda: self.gallery_scroll.verticalScrollBar().setValue(self._library_scroll_pos))

    def keyPressEvent(self, e):
        if self.stack.currentIndex() == 1:
            if e.key() == Qt.Key_Escape:
                self.back()
                return
            if e.key() == Qt.Key_Space:
                self.detail.player.toggle()
                return
        super().keyPressEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = max(1, (self.inner.width() + T.SP5) // (CARD_W + T.SP5))
        if cols != self._cols:
            self._cols = cols
            self._debounce.start(80)

    def _on_view(self, v):
        self.state.settings["library_view"] = v
        self.state.settings.save()
        self._render()

    def _clear_filters(self):
        for s in (self.f_plat, self.f_date, self.f_sync):
            s.setCurrentIndex(0)
        self.search.clear()

    def _filtered(self):
        plat, days, sync = self.f_plat.key(), self.f_date.key(), self.f_sync.key()
        q = self.search.text().strip().lower()
        now = time.time()
        out = []
        for c in self.state.clips:
            if plat != "all" and c.platform != plat:
                continue
            if days != "all" and now - c.mtime > int(days) * DAY:
                continue
            if sync != "all" and c.sync_state != sync:
                continue
            if q and q not in f"{c.title} {c.channel} {c.video_title} {c.hook} {c.name}".lower():
                continue
            out.append(c)
        sort = self.f_sort.key()
        key = {"recent": lambda c: -c.mtime, "old": lambda c: c.mtime,
               "long": lambda c: -(c.duration or 0), "short": lambda c: (c.duration or 1e9),
               "score": lambda c: -(c.score if c.score is not None else -1)}[sort]
        if sort != self.state.settings["library_sort"]:
            self.state.settings["library_sort"] = sort
            self.state.settings.save()
        return sorted(out, key=key)

    def _render(self):
        clear_layout(self.grid)
        clear_layout(self.list)
        total = len(self.state.clips)
        clips = self._filtered()
        filtered = len(clips) != total
        self.clear_f.setVisible(filtered or bool(self.search.text()))
        self.count.setText(f"{len(clips)} de {total} clipes" if filtered else f"{total} clipes")
        if not total:
            self.content.setCurrentWidget(self.empty_lib)
            return
        if not clips:
            self.content.setCurrentWidget(self.empty_res)
            return
        if self.view.value() == "list":
            for c in clips[:400]:
                self.list.addWidget(ListRow(c, self.open_clip))
            self.content.setCurrentWidget(self.list_host)
        else:
            cols = max(1, self._cols or 5)
            for i, c in enumerate(clips[:400]):
                plat, date, dur = clip_meta(c)
                card = VideoCard(c, CARD_W, plat, sync_info(c), date, dur)
                card.clicked.connect(self.open_clip)
                self.grid.addWidget(card, i // cols, i % cols)
            self.content.setCurrentWidget(self.grid_host)
