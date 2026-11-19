from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from .. import __version__
from .. import theme as T
from ..core import DEFAULT_TW_OUT, DEFAULT_YT_OUT, REPO, TWITCH, YOUTUBE
from ..storage import DATA_DIR, LOG_DIR
from ..system import find_claude
from ..widgets import Icon, NeonProgress, Spinner, badge, card, icon_button, label
from .common import Page, open_folder


class FolderRow(QWidget):
    def __init__(self, state, key: str, title: str, default: Path):
        super().__init__()
        self.state, self.key, self.default = state, key, default
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(6)
        v.addWidget(label(title))
        h = QHBoxLayout()
        self.edit = QLineEdit(state.settings[key])
        self.edit.setReadOnly(True)
        h.addWidget(self.edit, 1)
        b = icon_button("Escolher", "folder", "Ghost")
        b.clicked.connect(self._choose)
        o = icon_button("", "open", "Ghost", "Abrir no Explorer")
        o.setFixedWidth(40)
        o.clicked.connect(lambda: open_folder(Path(self.edit.text())))
        r = icon_button("Padrão", "refresh", "Ghost", f"Voltar para {default}")
        r.clicked.connect(lambda: self._set(str(default)))
        for x in (b, o, r):
            h.addWidget(x)
        v.addLayout(h)

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


class CheckRow(QFrame):
    def __init__(self, c):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 10, 6)
        h.setSpacing(10)
        col = T.GREEN if c.ok else (T.RED if c.required else T.AMBER)
        h.addWidget(Icon("check" if c.ok else "error", 13, col))
        n = label(c.name)
        n.setStyleSheet("font-weight: 600;")
        n.setFixedWidth(250)
        h.addWidget(n)
        d = label(c.detail, "Dim")
        d.setTextInteractionFlags(Qt.TextSelectableByMouse)
        d.setToolTip(c.detail)
        d.setMinimumWidth(10)
        h.addWidget(d, 1)
        h.addWidget(badge("OK" if c.ok else ("FALTA" if c.required else "OPCIONAL"), col))


class Settings(Page):
    def __init__(self, state):
        super().__init__("Configurações", "Pastas, dependências e placa de vídeo")
        self.state = state

        # pastas
        c = card("CardFlat")
        v = QVBoxLayout(c)
        v.setContentsMargins(22, 18, 22, 18)
        v.setSpacing(8)
        v.addWidget(label("Pastas de saída", "SectionTitle"))
        v.addWidget(FolderRow(state, "youtube_out", "Vídeos do YouTube (cortes-youtube)", DEFAULT_YT_OUT))
        v.addWidget(FolderRow(state, "twitch_out", "Lives da Twitch (clipar-gta-br)", DEFAULT_TW_OUT))
        v.addWidget(label("Com uma pasta diferente da padrão, o app pede ao Claude para salvar o job lá "
                          "(--out do prepare). A biblioteca sempre mostra também as pastas padrão. "
                          "O histórico de vídeos já cortados das skills continua na pasta padrão.", "Dim", wrap=True))
        cl = QHBoxLayout()
        cl.addWidget(label("Claude Code"))
        self.claude = QLineEdit(state.settings["claude_path"] or (find_claude() or ""))
        self.claude.setPlaceholderText("detectado automaticamente")
        self.claude.setReadOnly(True)
        cl.addWidget(self.claude, 1)
        cb = icon_button("Escolher", "terminal", "Ghost")
        cb.clicked.connect(self._choose_claude)
        cl.addWidget(cb)
        v.addSpacing(6)
        v.addLayout(cl)
        self.body.addWidget(c)

        row = QHBoxLayout()
        row.setSpacing(14)
        # dependências
        d = card("CardFlat")
        dv = QVBoxLayout(d)
        dv.setContentsMargins(22, 18, 22, 18)
        dh = QHBoxLayout()
        dh.addWidget(label("Dependências", "SectionTitle"))
        dh.addStretch(1)
        self.spin = Spinner(18)
        self.spin.hide()
        dh.addWidget(self.spin)
        self.b_check = icon_button("Verificar agora", "refresh", "Ghost")
        self.b_check.clicked.connect(state.refresh_checks)
        dh.addWidget(self.b_check)
        dv.addLayout(dh)
        self.checks = QVBoxLayout()
        self.checks.setSpacing(2)
        dv.addLayout(self.checks)
        self.fix = label("", "Dim", wrap=True)
        dv.addWidget(self.fix)
        dv.addStretch(1)
        row.addWidget(d, 3)

        # GPU
        g = card("CardFlat")
        g.setMinimumWidth(320)
        gv = QVBoxLayout(g)
        gv.setContentsMargins(22, 18, 22, 18)
        gv.setSpacing(10)
        gh = QHBoxLayout()
        gh.addWidget(Icon("gpu", 16, T.PINK))
        gh.addWidget(label("Placa de vídeo", "SectionTitle"), 1)
        gv.addLayout(gh)
        self.g_name = label("…")
        self.g_name.setStyleSheet("font-size: 17px; font-weight: 800;")
        gv.addWidget(self.g_name)
        self.g_grid = QGridLayout()
        self.g_grid.setVerticalSpacing(6)
        self.g_vals = {}
        for i, (k, t) in enumerate((("driver", "Driver"), ("cuda", "CUDA"), ("temp", "Temperatura"),
                                    ("util", "Uso"), ("trans", "Transcrição"), ("enc", "Codificador"))):
            self.g_grid.addWidget(label(t, "Dim"), i, 0)
            val = label("--")
            self.g_vals[k] = val
            self.g_grid.addWidget(val, i, 1)
        gv.addLayout(self.g_grid)
        gv.addWidget(label("Memória de vídeo", "Dim"))
        self.vram = NeonProgress()
        self.vram.setFixedHeight(10)
        gv.addWidget(self.vram)
        self.vram_lbl = label("", "Dim")
        gv.addWidget(self.vram_lbl)
        gv.addStretch(1)
        row.addWidget(g, 2)
        self.body.addLayout(row)

        # segurança / sobre
        s = card("CardFlat")
        sv = QVBoxLayout(s)
        sv.setContentsMargins(22, 18, 22, 18)
        sv.setSpacing(6)
        sv.addWidget(label("Segurança e privacidade", "SectionTitle"))
        for txt in ("O app roda as skills com as mesmas permissões dos rodar_automatico.ps1: só scripts Python, "
                    "leitura e escrita de arquivos. Nada é publicado.",
                    "Nenhum arquivo é apagado. Cancelar encerra os processos e mantém o que já foi gerado.",
                    "Credenciais e tokens são mascarados nos logs (••••••). Cookies do navegador nunca são usados "
                    "sem você pedir ao Claude.",
                    f"Logs e configurações do app: {DATA_DIR}"):
            r = QHBoxLayout()
            r.addWidget(Icon("shield", 12, T.PINK))
            r.addWidget(label(txt, "Muted", wrap=True), 1)
            sv.addLayout(r)
        bb = QHBoxLayout()
        lo = icon_button("Pasta de logs", "folder", "Ghost")
        lo.clicked.connect(lambda: (LOG_DIR.mkdir(parents=True, exist_ok=True), open_folder(LOG_DIR)))
        rp = icon_button("Pasta do projeto", "folder", "Ghost")
        rp.clicked.connect(lambda: open_folder(REPO))
        bb.addWidget(lo)
        bb.addWidget(rp)
        bb.addStretch(1)
        bb.addWidget(label(f"GTA CLIPPER STUDIO v{__version__}", "Dim"))
        sv.addLayout(bb)
        self.body.addWidget(s)
        self.body.addStretch(1)

        self.gpu_timer = QTimer(self)
        self.gpu_timer.timeout.connect(state.refresh_gpu)
        state.checks_changed.connect(self._render_checks)
        state.gpu_changed.connect(self._render_gpu)

    def on_show(self):
        self.state.refresh_gpu()
        self.gpu_timer.start(4000)
        if not self.state.checks:
            self.state.refresh_checks()

    def on_hide(self):
        self.gpu_timer.stop()

    def _choose_claude(self):
        f, _ = QFileDialog.getOpenFileName(self, "Onde está o claude.exe?", str(Path.home()), "claude (*.exe *.cmd)")
        if f:
            self.claude.setText(f)
            self.state.settings["claude_path"] = f
            self.state.settings.save()

    def _render_checks(self):
        busy = self.state.checking
        self.spin.setVisible(busy)
        self.b_check.setEnabled(not busy)
        if busy:
            return
        while self.checks.count():
            it = self.checks.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for c in self.state.checks:
            self.checks.addWidget(CheckRow(c))
        bad = [c for c in self.state.checks if c.required and not c.ok]
        self.fix.setText("Tudo certo para cortar." if not bad else
                         "Para resolver: abra o PowerShell na pasta do projeto, digite claude e peça "
                         "'configura o clipper'. Detalhes no README.")
        cfg = self.state.cfg
        if cfg:
            self.g_vals["trans"].setText(f"{cfg.get('device', '?').upper()} · {cfg.get('model', '?')}")
            self.g_vals["enc"].setText(cfg.get("encoder", "?"))

    def _render_gpu(self):
        g = self.state.gpu
        if not g.get("ok"):
            self.g_name.setText("Sem GPU NVIDIA")
            self.vram_lbl.setText(g.get("detail", ""))
            return
        self.g_name.setText(g["name"])
        self.g_vals["driver"].setText(g.get("driver", "--"))
        self.g_vals["cuda"].setText(g.get("cuda", "--"))
        try:
            self.g_vals["temp"].setText(f"{float(g['temp']):.0f} °C")
            self.g_vals["util"].setText(f"{float(g['util']):.0f} %")
            used, total = float(g["mem_used"]), float(g["mem_total"])
            self.vram.animate_to(100 * used / total if total else 0)
            self.vram_lbl.setText(f"{used / 1024:.1f} GB de {total / 1024:.1f} GB em uso")
        except (KeyError, ValueError):
            pass
