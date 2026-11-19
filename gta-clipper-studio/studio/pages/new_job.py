from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout

from .. import theme as T
from ..core import AUTO_LANG, LANGS, MAX_CLIPS, TWITCH, YOUTUBE, detect_platform, lang_name, validate_link
from ..widgets import AdaptiveBox, Icon, ReflowGrid, card, glow, glyph, icon_button, icon_font, label, set_button_enabled
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
        self.hint = label("Aceita vídeos do YouTube (de qualquer duração) e VODs da Twitch.", "Dim", wrap=True)
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
        prow = ReflowGrid(300, (2, 1), 14)
        self.p_yt = PlatformCard("video", "YouTube", "Vídeo de gameplay, qualquer duração · até 10 cortes\n"
                                 "legenda traduzida para pt-BR · skill cortes-youtube", "#ff4e45")
        self.p_tw = PlatformCard("sync", "Twitch", "Live/VOD longa com facecam · até 10 cortes\n"
                                 "live gringa: legenda traduzida para pt-BR · skill clipar-gta-br", T.PURPLE)
        self.pgroup = QButtonGroup(self)
        self.pgroup.setExclusive(True)
        for b in (self.p_yt, self.p_tw):
            self.pgroup.addButton(b)
            prow.add(b)
        self.p_yt.toggled.connect(self._on_platform)
        v2.addWidget(prow)
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
        crow = ReflowGrid(44, (10, 5), 10)
        self.cgroup = QButtonGroup(self)
        self.cbtns = []
        for n in range(1, max(MAX_CLIPS.values()) + 1):
            b = QPushButton(str(n))
            b.setObjectName("SegPurple")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(50)
            b.setMinimumWidth(36)
            self.cgroup.addButton(b, n)
            self.cbtns.append(b)
            crow.add(b)
        v3.addWidget(crow)
        v3.addWidget(label("É o máximo: se não houver momentos bons o bastante (nota acima de 6), sai menos. "
                           "2 cortes ótimos valem mais que 5 médios. 6 ou mais pede vídeo longo (1 h ou mais).",
                           "Dim", wrap=True))
        self.body.addWidget(c3)

        # idioma (só YouTube: o fluxo de lives é sempre em português)
        self.c4 = card("CardFlat")
        v4 = QVBoxLayout(self.c4)
        v4.setContentsMargins(22, 20, 22, 20)
        v4.setSpacing(12)
        v4.addWidget(label("4. Idioma do vídeo / live", "SectionTitle"))
        lrow = ReflowGrid(110, (4, 2), 10)
        self.lgroup = QButtonGroup(self)
        self.lgroup.setExclusive(True)
        self.lbtns: dict[str, QPushButton] = {}
        for code, name in LANGS.items():
            b = QPushButton(name)
            b.setObjectName("SegPurple")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(46)
            self.lgroup.addButton(b)
            self.lbtns[code] = b
            lrow.add(b)
            b.toggled.connect(self._on_lang)
        v4.addWidget(lrow)
        self.lang_hint = label("", "Dim", wrap=True)
        v4.addWidget(self.lang_hint)
        self.keep_orig = QCheckBox("Manter legenda no idioma original")
        self.keep_orig.setToolTip("Não traduz a legenda para português (hook, título e post continuam em pt-BR).")
        self.keep_orig.setCursor(Qt.PointingHandCursor)
        self.keep_orig.toggled.connect(self._on_lang)
        v4.addWidget(self.keep_orig)
        self.body.addWidget(self.c4)

        # iniciar
        foot = AdaptiveBox(760, 14)
        fh = foot.box
        fh.setContentsMargins(0, 6, 0, 0)
        sec = QVBoxLayout()
        sec.setSpacing(4)
        for ic, txt in (("shield", "Nada é publicado automaticamente: os vídeos ficam só no seu computador."),
                        ("check", "Usa as skills e scripts que já existem; nenhum arquivo é apagado."),
                        ("clock", "Com placa NVIDIA: ~3-5 min por vídeo de 1 h, ~10-15 min por vídeo/live de 4 h.")):
            r = QHBoxLayout()
            r.addWidget(Icon(ic, 13, T.ORANGE), 0, Qt.AlignTop)
            r.addWidget(label(txt, "Dim", wrap=True), 1)
            sec.addLayout(r)
        fh.addLayout(sec, 1)
        self.start_btn = icon_button("INICIAR PROCESSAMENTO", "rocket", "Primary")
        self.start_btn.setFixedHeight(56)
        self.start_btn.setMinimumWidth(240)
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
        last_lang = state.settings["last_lang"]
        self.lbtns.get(last_lang if last_lang in LANGS else AUTO_LANG).setChecked(True)
        self.keep_orig.setChecked(bool(state.settings["keep_original_captions"]))
        self._on_lang()
        self._on_url("")

    def lang(self) -> str:
        for code, b in self.lbtns.items():
            if b.isChecked():
                return code
        return AUTO_LANG

    def _on_lang(self, *_):
        code = self.lang()
        live = self.platform() == TWITCH
        if code == AUTO_LANG and live:
            txt = ("O Claude decide pelo título e pelo canal; se não for live brasileira, o Whisper detecta pelo "
                   "áudio. Live gringa ganha legenda traduzida para português. Se souber o idioma, escolha acima.")
        elif code == AUTO_LANG:
            txt = ("O Claude decide pelo título e pelo canal; na dúvida, o Whisper detecta pelo áudio. "
                   "Vídeo gringo ganha legenda traduzida para português. Se souber o idioma, escolha acima.")
        elif code == "pt":
            txt = f"{'Live brasileira' if live else 'Vídeo brasileiro'}: transcrição em português, sem tradução."
        elif self.keep_orig.isChecked():
            txt = (f"Transcrição e legenda em {lang_name(code)}, sem tradução. "
                   "Hook, título e post saem em português.")
        else:
            txt = (f"Transcrição em {lang_name(code)} (tempos exatos do áudio original) e legenda traduzida para "
                   "português (pt-BR). Hook, título e post saem em português.")
        if code == AUTO_LANG and self.keep_orig.isChecked():
            txt = (f"O Claude decide o idioma; se {'a live for gringa' if live else 'o vídeo for gringo'}, a legenda fica no "
                   "idioma original, sem tradução.")
        self.lang_hint.setText(txt)
        self.keep_orig.setVisible(code != "pt")

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
        if hasattr(self, "keep_orig"):
            self._on_lang()
        self._on_url(self.url.text())

    def _on_url(self, text: str):
        text = text.strip()
        found = detect_platform(text)
        if not text:
            self.hint_ic.set("info", T.MUTED)
            self.hint.setText("Aceita vídeos do YouTube (de qualquer duração) e VODs da Twitch.")
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
        job = {"url": url, "platform": self.platform(), "clips": n}
        lang = self.lang()
        self.state.settings["last_lang"] = lang
        job["lang"] = lang
        self.state.settings["keep_original_captions"] = self.keep_orig.isChecked()
        job["original_captions"] = self.keep_orig.isChecked() and lang != "pt"
        self.state.settings.save()
        self.state.job_started.emit(job)
