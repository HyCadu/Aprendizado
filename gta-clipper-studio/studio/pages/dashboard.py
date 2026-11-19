from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import theme as T
from ..storage import fmt_duration, library_stats
from ..widgets import Icon, PulseDot, StatCard, badge, card, glow, icon_button, label
from .common import PLATFORM_COLOR, PLATFORM_LABEL, STATUS_COLOR, Page, clip_thumb, rounded


class StatusRow(QWidget):
    def __init__(self, icon: str, name: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 6, 0, 6)
        h.setSpacing(12)
        h.addWidget(Icon(icon, 15, T.MUTED))
        v = QVBoxLayout()
        v.setSpacing(0)
        self.name = label(name)
        self.name.setStyleSheet("font-weight: 600;")
        self.detail = label("verificando…", "Dim")
        v.addWidget(self.name)
        v.addWidget(self.detail)
        h.addLayout(v, 1)
        self.dot = PulseDot(T.MUTED, 10)
        h.addWidget(self.dot)

    def set(self, ok: bool | None, detail: str):
        self.detail.setText(detail)
        if ok is None:
            self.dot.set_color(T.MUTED, True)
        else:
            self.dot.set_color(T.GREEN if ok else T.RED, pulsing=bool(ok))


class Dashboard(Page):
    def __init__(self, state):
        super().__init__("Dashboard", "Resumo dos seus cortes e do sistema")
        self.state = state
        new_btn = icon_button("NOVO CORTE", "add", "Primary")
        new_btn.setFixedHeight(42)
        glow(new_btn, T.PINK, 30, 110)
        new_btn.clicked.connect(lambda: state.navigate.emit("new"))
        self.head_right.addWidget(new_btn)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.s_clips = StatCard("video", "Cortes gerados", T.PINK)
        self.s_jobs = StatCard("cut", "Vídeos processados", T.PURPLE)
        self.s_week = StatCard("clock", "Nos últimos 7 dias", T.CYAN)
        self.s_time = StatCard("star", "Tempo total de cortes", T.ORANGE)
        for i, w in enumerate((self.s_clips, self.s_jobs, self.s_week, self.s_time)):
            grid.addWidget(w, 0, i)
        self.body.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(14)
        # status do sistema
        sys_card = card()
        sv = QVBoxLayout(sys_card)
        sv.setContentsMargins(20, 18, 20, 14)
        sh = QHBoxLayout()
        sh.addWidget(label("Status do sistema", "SectionTitle"))
        sh.addStretch(1)
        self.overall = badge("verificando", T.MUTED)
        sh.addWidget(self.overall)
        sv.addLayout(sh)
        sv.addSpacing(4)
        self.r_claude = StatusRow("terminal", "Claude Code")
        self.r_skills = StatusRow("rocket", "Skills de corte")
        self.r_gpu = StatusRow("gpu", "Placa de vídeo")
        self.r_trans = StatusRow("chip", "Transcrição")
        self.r_ff = StatusRow("video", "FFmpeg")
        for r in (self.r_claude, self.r_skills, self.r_gpu, self.r_trans, self.r_ff):
            sv.addWidget(r)
        sv.addStretch(1)
        row.addWidget(sys_card, 4)

        # últimos processamentos
        rec = card()
        rv = QVBoxLayout(rec)
        rv.setContentsMargins(20, 18, 20, 18)
        rh = QHBoxLayout()
        rh.addWidget(label("Últimos processamentos", "SectionTitle"))
        rh.addStretch(1)
        rv.addLayout(rh)
        self.recent = QVBoxLayout()
        self.recent.setSpacing(6)
        rv.addLayout(self.recent)
        rv.addStretch(1)
        row.addWidget(rec, 6)
        self.body.addLayout(row)

        # cortes recentes
        cl = card()
        cv = QVBoxLayout(cl)
        cv.setContentsMargins(20, 18, 20, 18)
        ch = QHBoxLayout()
        ch.addWidget(label("Cortes recentes", "SectionTitle"))
        ch.addStretch(1)
        lib = icon_button("Ver biblioteca", "library", "Ghost")
        lib.clicked.connect(lambda: state.navigate.emit("library"))
        ch.addWidget(lib)
        cv.addLayout(ch)
        self.thumbs = QHBoxLayout()
        self.thumbs.setSpacing(14)
        cv.addLayout(self.thumbs)
        self.body.addWidget(cl)
        self.body.addStretch(1)

        state.clips_changed.connect(self._render_clips)
        state.checks_changed.connect(self._render_checks)
        state.gpu_changed.connect(self._render_checks)
        state.history_changed.connect(self._render_recent)
        state.clips_changed.connect(self._render_recent)

    def on_show(self):
        self.state.refresh_clips()

    # ------------------------------------------------------------
    def _render_clips(self):
        st = library_stats(self.state.clips)
        self.s_clips.set_value(st["clips"])
        self.s_jobs.set_value(st["jobs"])
        self.s_week.set_value(st["week"])
        self.s_time.set_value(0, text=fmt_duration(st["seconds"]) if st["seconds"] else "0:00")
        while self.thumbs.count():
            it = self.thumbs.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        clips = self.state.clips[:6]
        if not clips:
            self.thumbs.addWidget(label("Nenhum corte ainda. Clique em NOVO CORTE para começar.", "Muted"))
        for c in clips:
            self.thumbs.addWidget(self._thumb(c))
        self.thumbs.addStretch(1)

    def _thumb(self, c):
        w = QFrame()
        w.setCursor(Qt.PointingHandCursor)
        w.setFixedWidth(126)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        img = QLabel()
        img.setPixmap(rounded(clip_thumb(c.sheet, 126, c.mtime), 10))
        img.setFixedSize(126, 224)
        img.setToolTip(f"{c.title}\n{c.name}")
        v.addWidget(img)
        t = label(c.title, wrap=True)
        t.setStyleSheet("font-size: 11px; font-weight: 600;")
        t.setMaximumHeight(32)
        v.addWidget(t)
        w.mousePressEvent = lambda _e, clip=c: self.state.play_clip.emit(clip)
        return w

    def _render_recent(self):
        while self.recent.count():
            it = self.recent.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        items = self.state.history.merged(self.state.settings)[:6]
        if not items:
            self.recent.addWidget(label("Nenhum processamento ainda.", "Muted"))
            return
        for it in items:
            self.recent.addWidget(self._recent_row(it))

    def _recent_row(self, it: dict) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f"QFrame {{ background: {T.SURFACE_2}; border-radius: 10px; }}")
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)
        plat = it.get("platform", "")
        h.addWidget(Icon("video" if plat == "youtube" else "sync", 14, PLATFORM_COLOR.get(plat, T.MUTED)))
        v = QVBoxLayout()
        v.setSpacing(0)
        title = it.get("title") or it.get("url", "")
        t = label(title)
        t.setStyleSheet("background: transparent; font-weight: 600;")
        t.setMaximumWidth(420)
        t.setToolTip(it.get("url", ""))
        fm = t.fontMetrics()
        t.setText(fm.elidedText(title, Qt.ElideRight, 400))
        sub = f"{PLATFORM_LABEL.get(plat, plat)} · {it.get('when', '')}"
        if it.get("clips") is not None:
            sub += f" · {it['clips']} corte(s)"
        if it.get("note"):
            sub += f" · {it['note']}"
        s = label(sub, "Dim")
        s.setStyleSheet("background: transparent;")
        v.addWidget(t)
        v.addWidget(s)
        h.addLayout(v, 1)
        status = it.get("status", "?")
        h.addWidget(badge(status.upper(), STATUS_COLOR.get(status, T.MUTED)))
        return w

    def _render_checks(self):
        st = self.state
        if st.checking and not st.checks:
            return
        c = st.check("Claude Code")
        self.r_claude.set(c.ok if c else None, c.detail.split("·")[0].strip() if c else "")
        skills = [x for x in st.checks if x.name.startswith("Skill")]
        if skills:
            ok = all(x.ok for x in skills)
            self.r_skills.set(ok, "cortes-youtube · clipar-gta-br · ai-stream-clipper" if ok else
                              "Falta: " + ", ".join(x.name.replace("Skill ", "") for x in skills if not x.ok))
        g = st.gpu
        if g:
            if g.get("ok"):
                parts = [g["name"]]
                try:
                    parts.append(f"{round(float(g['mem_total']) / 1024)} GB")
                except (KeyError, ValueError):
                    pass
                try:
                    parts.append(f"{float(g['temp']):.0f} °C")
                except (KeyError, ValueError):
                    if g.get("api"):  # AMD / Intel Arc: sem temperatura no Windows; mostra o modo de transcrição
                        parts.append(g["api"])
                self.r_gpu.set(True, " · ".join(parts))
            else:
                self.r_gpu.set(False, g.get("detail", "sem placa de vídeo dedicada"))
        cfg = st.cfg
        if st.checks:
            if cfg:
                dev = cfg.get("device", "cpu").upper()
                self.r_trans.set(True, f"{dev} · modelo {cfg.get('model', '?')} · {cfg.get('encoder', '?')}")
            else:
                self.r_trans.set(False, "Setup do clipper não feito")
        f = st.check("FFmpeg")
        if f:
            self.r_ff.set(f.ok, (f.detail.split("·")[0].strip()[:48]) if f.ok else f.detail)
        if st.checks:
            req_fail = [x for x in st.checks if x.required and not x.ok]
            self.overall.setText("PRONTO" if not req_fail else f"{len(req_fail)} PENDÊNCIA(S)")
            col = T.GREEN if not req_fail else T.AMBER
            self.overall.setStyleSheet(badge("", col).styleSheet())
