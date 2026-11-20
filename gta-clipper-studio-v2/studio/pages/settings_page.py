"""Configurações: geral, processamento, legendas, hardware, dependências e diagnóstico."""
from __future__ import annotations

import platform
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter
from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from .. import __version__
from .. import theme as T
from ..core import DEFAULT_TW_OUT, DEFAULT_YT_OUT, LEGENDAS, MAX_CLIPS, REPO, TWITCH, YOUTUBE
from ..storage import DATA_DIR, LOG_DIR
from ..system import find_claude, launch_claude_login
from ..widgets import Badge, Icon, SectionHeader, Select, Spinner, button, clear_layout, label, panel
from .common import Page, open_file, open_folder


class Meter(QWidget):
    """Barra fina de uso (memória de vídeo)."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(6)
        self.value = 0.0

    def set(self, v: float):
        self.value = max(0.0, min(1.0, v))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        r = QRectF(0, 0, self.width(), self.height())
        p.setBrush(QColor(T.BORDER))
        p.drawRoundedRect(r, 3, 3)
        if self.value > 0:
            col = T.ERROR if self.value > 0.9 else (T.WARNING if self.value > 0.75 else T.PRIMARY)
            p.setBrush(QColor(col))
            p.drawRoundedRect(QRectF(0, 0, max(6, r.width() * self.value), r.height()), 3, 3)


def section(title: str, subtitle: str = "", right: QWidget | None = None):
    box = panel("Panel")
    v = QVBoxLayout(box)
    v.setContentsMargins(T.SP5, T.SP5, T.SP5, T.SP5)
    v.setSpacing(T.SP4)
    v.addWidget(SectionHeader(title, subtitle, right))
    return box, v


def field_row(name: str, widget: QWidget, hint: str = "") -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(T.SP4)
    left = QVBoxLayout()
    left.setSpacing(2)
    left.addWidget(label(name, "H3"))
    if hint:
        left.addWidget(label(hint, "Dim", wrap=True))
    lw = QWidget()
    lw.setLayout(left)
    lw.setFixedWidth(240)
    h.addWidget(lw)
    h.addWidget(widget, 1)
    return w


class FolderPicker(QWidget):
    def __init__(self, state, key: str, default: Path):
        super().__init__()
        self.state, self.key, self.default = state, key, default
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(T.SP2)
        self.edit = QLineEdit(state.settings[key])
        self.edit.setReadOnly(True)
        h.addWidget(self.edit, 1)
        b = button("Escolher", "folder")
        b.clicked.connect(self._choose)
        o = button("", "open", "Ghost", "Abrir no Explorer")
        o.clicked.connect(lambda: open_folder(Path(self.edit.text())))
        r = button("", "refresh", "Ghost", f"Voltar para o padrão ({default})")
        r.clicked.connect(lambda: self._set(str(default)))
        for x in (b, o, r):
            h.addWidget(x)

    def _choose(self):
        d = QFileDialog.getExistingDirectory(self, "Escolher pasta de saída", self.edit.text())
        if d:
            self._set(str(Path(d)))

    def _set(self, path: str):
        if any(c in path for c in "\"`\r\n"):
            self.state.toast.emit("Pasta com caracteres inválidos.", "error")
            return
        self.edit.setText(path)
        self.state.settings[self.key] = path
        self.state.settings.save()
        self.state.refresh_clips()
        self.state.toast.emit("Pasta de saída salva.", "info")


class CheckRow(QWidget):
    def __init__(self, c):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 4, 0, 4)
        h.setSpacing(T.SP3)
        col = T.SUCCESS if c.ok else (T.ERROR if c.required else T.WARNING)
        h.addWidget(Icon("check" if c.ok else ("error" if c.required else "warn"), 12, col))
        n = label(c.name)
        n.setFixedWidth(250)
        h.addWidget(n)
        d = label("", "Dim")
        d.setTextInteractionFlags(Qt.TextSelectableByMouse)
        d.setToolTip(c.detail)
        d.setText(d.fontMetrics().elidedText(c.detail, Qt.ElideMiddle, 520))
        d.setMinimumWidth(10)
        h.addWidget(d, 1)
        if not c.ok:
            h.addWidget(Badge("Falta" if c.required else "Opcional", col))


class Settings(Page):
    def __init__(self, state):
        super().__init__(max_width=880)
        self.state = state
        head = QVBoxLayout()
        head.setSpacing(2)
        head.addWidget(label("Configurações", "H1"))
        head.addWidget(label("Pastas, processamento, legendas e diagnóstico.", "Muted"))
        self.body.addLayout(head)

        # ---------------------------------------------- geral
        box, v = section("Geral")
        v.addWidget(field_row("Vídeos do YouTube", FolderPicker(state, "youtube_out", DEFAULT_YT_OUT),
                              "Onde o cortes-youtube salva os jobs."))
        v.addWidget(field_row("Lives", FolderPicker(state, "twitch_out", DEFAULT_TW_OUT),
                              "Onde o clipar-gta-br salva os jobs."))
        cl = QWidget()
        ch = QHBoxLayout(cl)
        ch.setContentsMargins(0, 0, 0, 0)
        ch.setSpacing(T.SP2)
        self.claude = QLineEdit(state.settings["claude_path"] or (find_claude() or ""))
        self.claude.setPlaceholderText("detectado automaticamente")
        self.claude.setReadOnly(True)
        ch.addWidget(self.claude, 1)
        cb = button("Escolher", "terminal")
        cb.clicked.connect(self._choose_claude)
        ch.addWidget(cb)
        v.addWidget(field_row("Claude Code", cl, "Executa as skills de corte."))
        lang = Select([("pt-BR", "Português (Brasil)")])
        lang.setEnabled(False)
        v.addWidget(field_row("Idioma do app", lang, "Único idioma disponível por enquanto."))
        self.body.addWidget(box)

        # ---------------------------------------------- autenticação
        box, v = section("Autenticação do Claude Code",
                         "Use o login oficial do Claude Code instalado neste computador.")
        auth_row = QHBoxLayout()
        auth_row.setSpacing(T.SP3)
        self.auth_spinner = Spinner(14)
        self.auth_spinner.hide()
        auth_row.addWidget(self.auth_spinner)
        self.auth_icon = Icon("info", 14, T.DIM)
        auth_row.addWidget(self.auth_icon)
        auth_text = QVBoxLayout()
        auth_text.setSpacing(2)
        self.auth_title = label("Verificando", "H3")
        self.auth_detail = label("Verificando a autenticação do Claude Code.", "Dim", wrap=True)
        auth_text.addWidget(self.auth_title)
        auth_text.addWidget(self.auth_detail)
        auth_row.addLayout(auth_text, 1)
        v.addLayout(auth_row)
        auth_actions = QHBoxLayout()
        auth_actions.addStretch(1)
        self.b_authenticate = button("Autenticar", "terminal", "Primary")
        self.b_authenticate.clicked.connect(self._authenticate)
        auth_actions.addWidget(self.b_authenticate)
        self.b_auth_check = button("Verificar novamente", "refresh")
        self.b_auth_check.clicked.connect(state.refresh_auth_status)
        auth_actions.addWidget(self.b_auth_check)
        v.addLayout(auth_actions)
        self.body.addWidget(box)

        # ---------------------------------------------- processamento
        box, v = section("Processamento", "Definido pelo setup das skills. Para mudar, peça no Claude: "
                                          "configura o clipper.")
        self.proc = QGridLayout()
        self.proc.setHorizontalSpacing(T.SP6)
        self.proc.setVerticalSpacing(T.SP2)
        self.proc.setColumnStretch(1, 1)
        v.addLayout(self.proc)
        self.body.addWidget(box)

        # ---------------------------------------------- legendas
        box, v = section("Legendas")
        self.def_lang = Select([(k, t) for k, t in LEGENDAS.items()])
        self.def_lang.set_key(state.settings["default_legenda"])
        self.def_lang.currentIndexChanged.connect(self._save_lang)
        v.addWidget(field_row("Idioma padrão", self.def_lang,
                              "Pré-selecionado em Criar cortes. A skill traduz quando o vídeo é em outro idioma."))
        for name, text in (
                ("Sincronia", "Medida em cada clipe: fala ±40 ms e destaque da legenda ±120 ms (no report.md)."),
                ("Ajuste fino", "Se a legenda parecer adiantada ou atrasada, peça no Claude: "
                                "\"a legenda do clipe 2 está atrasada, ajusta\"."),
                ("Palavrões", "Mascarados na legenda e no título (P*RRA, F*CK).")):
            v.addWidget(field_row(name, label(text, "Muted", wrap=True)))
        self.body.addWidget(box)

        # ---------------------------------------------- hardware
        box, v = section("Hardware")
        self.hw = QGridLayout()
        self.hw.setHorizontalSpacing(T.SP6)
        self.hw.setVerticalSpacing(T.SP2)
        self.hw.setColumnStretch(1, 1)
        self.hw_vals = {}
        for i, (k, t) in enumerate((("name", "Placa de vídeo"), ("driver", "Driver / CUDA"), ("temp", "Temperatura"),
                                    ("util", "Uso"), ("device", "Processamento"))):
            self.hw.addWidget(label(t, "Label"), i, 0)
            val = label("--")
            self.hw_vals[k] = val
            self.hw.addWidget(val, i, 1)
        v.addLayout(self.hw)
        mv = QVBoxLayout()
        mv.setSpacing(T.SP1)
        mh = QHBoxLayout()
        mh.addWidget(label("Memória de vídeo", "Label"))
        mh.addStretch(1)
        self.vram_lbl = label("", "Dim")
        mh.addWidget(self.vram_lbl)
        mv.addLayout(mh)
        self.vram = Meter()
        mv.addWidget(self.vram)
        v.addLayout(mv)
        self.body.addWidget(box)

        # ---------------------------------------------- dependências
        right = QWidget()
        rh = QHBoxLayout(right)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(T.SP2)
        self.spin = Spinner(14)
        self.spin.hide()
        rh.addWidget(self.spin)
        self.b_check = button("Verificar agora", "refresh")
        self.b_check.clicked.connect(state.refresh_checks)
        rh.addWidget(self.b_check)
        box, v = section("Dependências", "Python, Claude Code, FFmpeg, skills e transcrição.", right)
        self.checks = QVBoxLayout()
        self.checks.setSpacing(0)
        v.addLayout(self.checks)
        self.fix = label("", "Dim", wrap=True)
        v.addWidget(self.fix)
        self.body.addWidget(box)

        # ---------------------------------------------- diagnóstico
        box, v = section("Diagnóstico", "Nada é publicado e nenhum arquivo é apagado. Credenciais aparecem "
                                        "mascaradas nos logs.")
        row = QHBoxLayout()
        row.setSpacing(T.SP2)
        lo = button("Pasta de logs", "folder")
        lo.clicked.connect(lambda: (LOG_DIR.mkdir(parents=True, exist_ok=True), open_folder(LOG_DIR)))
        last = button("Último log", "doc")
        last.clicked.connect(self._open_last_log)
        dd = button("Dados do app", "folder")
        dd.clicked.connect(lambda: (DATA_DIR.mkdir(parents=True, exist_ok=True), open_folder(DATA_DIR)))
        rp = button("Pasta do projeto", "folder")
        rp.clicked.connect(lambda: open_folder(REPO))
        info = button("Copiar informações técnicas", "copy", "Ghost")
        info.clicked.connect(self._copy_info)
        for b in (lo, last, dd, rp):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(info)
        v.addLayout(row)
        v.addWidget(label(f"GTA Clipper Studio v{__version__}  ·  {DATA_DIR}", "Dim"))
        self.body.addWidget(box)
        self.body.addStretch(1)

        self.gpu_timer = QTimer(self)
        self.gpu_timer.timeout.connect(state.refresh_gpu)
        state.checks_changed.connect(self._render_checks)
        state.auth_changed.connect(self._render_auth)
        state.gpu_changed.connect(self._render_gpu)
        self._render_auth()

    # ------------------------------------------------------------
    def on_show(self):
        self.state.refresh_gpu()
        self.gpu_timer.start(4000)
        if not self.state.checks:
            self.state.refresh_checks()
        self._render_checks()

    def on_hide(self):
        self.gpu_timer.stop()

    def _save_lang(self):
        self.state.settings["default_legenda"] = self.def_lang.key()
        self.state.settings.save()
        self.state.default_lang_changed.emit(self.def_lang.key())

    def _choose_claude(self):
        f, _ = QFileDialog.getOpenFileName(self, "Onde está o claude.exe?", str(Path.home()), "claude (*.exe *.cmd)")
        if f:
            self.claude.setText(f)
            self.state.settings["claude_path"] = f
            self.state.settings.save()
            self.state.refresh_checks()
            self.state.refresh_auth_status()

    def _authenticate(self):
        ok, message = launch_claude_login(self.state.settings["claude_path"])
        self.auth_detail.setText(message)
        self.state.toast.emit(message, "info" if ok else "error")

    def _render_auth(self):
        status = self.state.auth_status
        labels = {
            "connected": ("Conectado", "check", T.SUCCESS),
            "disconnected": ("Desconectado", "warn", T.WARNING),
            "checking": ("Verificando", "info", T.PRIMARY),
            "unavailable": ("Indisponível", "error", T.DIM),
            "auth_error": ("Erro de autenticação", "error", T.ERROR),
        }
        title, icon, color = labels.get(status, ("Indisponível", "error", T.DIM))
        self.auth_title.setText(title)
        self.auth_detail.setText(self.state.auth_detail)
        self.auth_spinner.setVisible(status == "checking")
        self.auth_icon.setVisible(status != "checking")
        self.auth_icon.set(icon, color)
        self.b_auth_check.setEnabled(status != "checking")
        self.b_authenticate.setEnabled(status != "checking" and bool(find_claude(self.state.settings["claude_path"])))

    def _open_last_log(self):
        logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True) if LOG_DIR.is_dir() else []
        if logs:
            open_file(logs[0])
        else:
            self.state.toast.emit("Nenhum log ainda.", "warn")

    def _copy_info(self):
        cfg, g = self.state.cfg, self.state.gpu
        lines = [f"GTA Clipper Studio {__version__}", f"Sistema: {platform.platform()}",
                 f"Python do app: {sys.version.split()[0]}", f"Projeto: {REPO}",
                 f"Transcrição: {cfg.get('device', '?')} · {cfg.get('model', '?')} · encoder {cfg.get('encoder', '?')}",
                 f"GPU: {g.get('name', g.get('detail', '?'))}"]
        lines += [f"[{'OK' if c.ok else '--'}] {c.name}: {c.detail}" for c in self.state.checks]
        QGuiApplication.clipboard().setText("\n".join(lines))
        self.state.toast.emit("Informações técnicas copiadas.", "info")

    def _render_checks(self):
        busy = self.state.checking
        self.spin.setVisible(busy)
        self.b_check.setEnabled(not busy)
        if busy:
            return
        clear_layout(self.checks)
        for c in self.state.checks:
            self.checks.addWidget(CheckRow(c))
        bad = [c for c in self.state.checks if c.required and not c.ok]
        self.fix.setText("Tudo certo para cortar." if not bad else
                         "Para resolver: abra o PowerShell na pasta do projeto, digite claude e peça "
                         "\"configura o clipper\". Detalhes no README.")
        clear_layout(self.proc)
        cfg = self.state.cfg
        rows = [("Transcrição", f"{cfg.get('device', '?').upper()} · modelo {cfg.get('model', '?')}" if cfg
                 else "Setup do clipper não feito"),
                ("Modelo reserva (CPU)", cfg.get("cpu_model", "--") if cfg else "--"),
                ("Codificação de vídeo", cfg.get("encoder", "--") if cfg else "--"),
                ("Vídeos do YouTube", f"cortes-youtube · até {MAX_CLIPS[YOUTUBE]} cortes · qualquer duração"),
                ("Lives", f"clipar-gta-br · até {MAX_CLIPS[TWITCH]} cortes")]
        for i, (k, val) in enumerate(rows):
            self.proc.addWidget(label(k, "Label"), i, 0)
            self.proc.addWidget(label(val), i, 1)
        self.hw_vals["device"].setText((f"{cfg.get('device', 'cpu').upper()} ({cfg.get('model', '?')})") if cfg else "--")

    def _render_gpu(self):
        g = self.state.gpu
        if not g.get("ok"):
            self.hw_vals["name"].setText("Sem GPU NVIDIA")
            self.vram_lbl.setText(g.get("detail", ""))
            return
        self.hw_vals["name"].setText(g["name"])
        self.hw_vals["driver"].setText(f"{g.get('driver', '--')}  ·  CUDA {g.get('cuda', '--')}")
        try:
            self.hw_vals["temp"].setText(f"{float(g['temp']):.0f} °C")
            self.hw_vals["util"].setText(f"{float(g['util']):.0f} %")
            used, total = float(g["mem_used"]), float(g["mem_total"])
            self.vram.set(used / total if total else 0)
            self.vram_lbl.setText(f"{used / 1024:.1f} de {total / 1024:.1f} GB")
        except (KeyError, ValueError):
            pass
