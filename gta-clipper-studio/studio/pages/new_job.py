from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from .. import theme as T
from ..core import MAX_CLIPS, TWITCH, YOUTUBE, detect_platform, validate_link
from ..widgets import Icon, card, glow, glyph, icon_button, icon_font, label, set_button_enabled
from .common import Page


class PlatformCard(QPushButton):
    def __init__(self, icon: str, title: str, sub: str, color: str):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(92)
        self.color = color
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 14, 18, 14)
        h.setSpacing(14)
        self.ic = label(glyph(icon))
        self.ic.setFont(icon_font(22))
        self.ic.setFixedSize(46, 46)
        self.ic.setAlignment(Qt.AlignCenter)
        v = QVBoxLayout()
        v.setSpacing(2)
        self.t = label(title)
        self.s = label(sub, wrap=True)
        v.addWidget(self.t)
        v.addWidget(self.s)
        self.check = label(glyph("check"))
        self.check.setFont(icon_font(14))
        for w in (self.ic, self.t, self.s, self.check):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        h.addWidget(self.ic)
        h.addLayout(v, 1)
        h.addWidget(self.check)
        self.toggled.connect(self._style)
        self._style(False)

    def _style(self, on: bool):
        c = self.color
        self.setStyleSheet(
            f"QPushButton {{ background: {'rgba(255,45,149,0.08)' if on else T.SURFACE_2};"
            f" border: 1px solid {T.PINK if on else T.BORDER}; border-radius: 14px; }}"
            f"QPushButton:hover {{ border-color: {T.PINK if on else '#4a3a66'}; }}")
        self.ic.setStyleSheet(f"color: {c}; background: rgba(255,255,255,0.04); border-radius: 12px;")
        self.t.setStyleSheet("background: transparent; font-size: 15px; font-weight: 800;")
        self.s.setStyleSheet(f"background: transparent; color: {T.MUTED}; font-size: 12px;")
        self.check.setStyleSheet(f"background: transparent; color: {T.PINK if on else 'transparent'};")


class NewJob(Page):
    def __init__(self, state):
        super().__init__("Novo corte", "Cole o link, escolha a origem e quantos cortes quer")
        self.state = state

        # link
        c1 = card("CardFlat")
        v1 = QVBoxLayout(c1)
        v1.setContentsMargins(22, 20, 22, 20)
        v1.setSpacing(10)
        v1.addWidget(label("1. Link do vídeo", "SectionTitle"))
        row = QHBoxLayout()
        self.url = QLineEdit()
        self.url.setObjectName("Big")
        self.url.setPlaceholderText("https://www.youtube.com/watch?v=…   ou   https://www.twitch.tv/videos/…")
        self.url.setClearButtonEnabled(True)
        self.url.textChanged.connect(self._on_url)
        self.url.returnPressed.connect(self._start)
        row.addWidget(self.url, 1)
        paste = icon_button("Colar", "paste", "Ghost")
        paste.setFixedHeight(48)
        paste.clicked.connect(self._paste)
        row.addWidget(paste)
        v1.addLayout(row)
        hint = QHBoxLayout()
        self.hint_ic = Icon("info", 13, T.MUTED)
        self.hint = label("Aceita vídeos do YouTube (até 60 min no modo vídeo) e VODs da Twitch.", "Dim")
        hint.addWidget(self.hint_ic)
        hint.addWidget(self.hint, 1)
        v1.addLayout(hint)
        self.body.addWidget(c1)

        # origem
        c2 = card("CardFlat")
        v2 = QVBoxLayout(c2)
        v2.setContentsMargins(22, 20, 22, 20)
        v2.setSpacing(12)
        v2.addWidget(label("2. Origem", "SectionTitle"))
        prow = QHBoxLayout()
        prow.setSpacing(14)
        self.p_yt = PlatformCard("video", "YouTube", "Vídeo editado de gameplay, até 60 min · até 5 cortes\n"
                                 "skill cortes-youtube", "#ff4e45")
        self.p_tw = PlatformCard("sync", "Twitch", "Live/VOD longa com facecam · até 3 cortes\n"
                                 "skill clipar-gta-br", T.PURPLE)
        self.pgroup = QButtonGroup(self)
        self.pgroup.setExclusive(True)
        for b in (self.p_yt, self.p_tw):
            self.pgroup.addButton(b)
            prow.addWidget(b, 1)
        self.p_yt.toggled.connect(self._on_platform)
        v2.addLayout(prow)
        self.body.addWidget(c2)

        # quantidade
        c3 = card("CardFlat")
        v3 = QVBoxLayout(c3)
        v3.setContentsMargins(22, 20, 22, 20)
        v3.setSpacing(12)
        h3 = QHBoxLayout()
        h3.addWidget(label("3. Quantidade de cortes", "SectionTitle"))
        h3.addStretch(1)
        self.count_hint = label("", "Dim")
        h3.addWidget(self.count_hint)
        v3.addLayout(h3)
        crow = QHBoxLayout()
        crow.setSpacing(10)
        self.cgroup = QButtonGroup(self)
        self.cbtns = []
        for n in range(1, 6):
            b = QPushButton(str(n))
            b.setObjectName("SegPurple")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(54)
            self.cgroup.addButton(b, n)
            self.cbtns.append(b)
            crow.addWidget(b)
        v3.addLayout(crow)
        v3.addWidget(label("É o máximo: se não houver momentos bons o bastante (nota acima de 6), sai menos. "
                           "2 cortes ótimos valem mais que 5 médios.", "Dim", wrap=True))
        self.body.addWidget(c3)

        # iniciar
        foot = QFrame()
        fh = QHBoxLayout(foot)
        fh.setContentsMargins(0, 6, 0, 0)
        sec = QVBoxLayout()
        sec.setSpacing(4)
        for ic, txt in (("shield", "Nada é publicado automaticamente: os vídeos ficam só no seu computador."),
                        ("check", "Usa as skills e scripts que já existem; nenhum arquivo é apagado."),
                        ("clock", "Com placa NVIDIA: ~3-5 min por vídeo de até 60 min, ~10-15 min por live de 4 h.")):
            r = QHBoxLayout()
            r.addWidget(Icon(ic, 13, T.ORANGE))
            r.addWidget(label(txt, "Dim"), 1)
            sec.addLayout(r)
        fh.addLayout(sec, 1)
        self.start_btn = icon_button("INICIAR PROCESSAMENTO", "rocket", "Primary")
        self.start_btn.setFixedHeight(56)
        self.start_btn.setMinimumWidth(300)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._start)
        self.start_glow = glow(self.start_btn, T.PINK, 40, 140)
        fh.addWidget(self.start_btn)
        self.body.addWidget(foot)
        self.body.addStretch(1)

        last = state.settings["last_platform"]
        (self.p_tw if last == TWITCH else self.p_yt).setChecked(True)
        self._on_platform()
        n = int(state.settings["last_clips"] or 3)
        b = self.cgroup.button(min(n, MAX_CLIPS[self.platform()]))
        if b:
            b.setChecked(True)
        self._on_url("")

    def platform(self) -> str:
        return TWITCH if self.p_tw.isChecked() else YOUTUBE

    def _paste(self):
        self.url.setText(QGuiApplication.clipboard().text().strip())

    def _on_platform(self, *_):
        mx = MAX_CLIPS[self.platform()]
        for i, b in enumerate(self.cbtns, 1):
            b.setEnabled(i <= mx)
        cur = self.cgroup.checkedId()
        if cur > mx:
            self.cgroup.button(mx).setChecked(True)
        self.count_hint.setText(f"de 1 a {mx}")
        self._on_url(self.url.text())

    def _on_url(self, text: str):
        text = text.strip()
        found = detect_platform(text)
        if not text:
            self.hint_ic.set("info", T.MUTED)
            self.hint.setText("Aceita vídeos do YouTube (até 60 min no modo vídeo) e VODs da Twitch.")
        elif found:
            ok, msg = validate_link(text, self.platform())
            if ok:
                self.hint_ic.set("check", T.GREEN)
                self.hint.setText(f"Link do {'YouTube' if found == YOUTUBE else 'Twitch'} reconhecido.")
            else:
                self.hint_ic.set("warn", T.AMBER)
                self.hint.setText(msg)
        else:
            self.hint_ic.set("warn", T.AMBER)
            ok, msg = validate_link(text, self.platform())
            self.hint.setText(msg)
        if found == TWITCH and not self.p_tw.isChecked():
            self.p_tw.setChecked(True)
        self.set_running(self.state.job_running)

    def set_running(self, running: bool):
        ok, _ = validate_link(self.url.text(), self.platform())
        set_button_enabled(self.start_btn, ok and not running)
        self.start_glow.setEnabled(ok and not running)
        self.start_btn.setToolTip("Já existe um processamento em andamento." if running else "")

    def _start(self):
        if self.state.job_running:
            self.state.toast.emit("Já existe um processamento em andamento.", "warn")
            return
        url = self.url.text().strip()
        ok, msg = validate_link(url, self.platform())
        if not ok:
            self.state.toast.emit(msg, "warn")
            return
        n = self.cgroup.checkedId()
        self.state.settings["last_platform"] = self.platform()
        self.state.settings["last_clips"] = n
        self.state.settings.save()
        self.state.job_started.emit({"url": url, "platform": self.platform(), "clips": n})
