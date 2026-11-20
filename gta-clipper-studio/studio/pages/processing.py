from __future__ import annotations

import html
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QMessageBox, QPlainTextEdit, QStackedLayout,
                               QTextBrowser, QVBoxLayout, QWidget)

from .. import theme as T
from ..core import AUTO_LANG, LANGS, STEP_INDEX, STEPS, TWITCH, Event, build_command, lang_name
from ..runner import JobRunner
from ..storage import LOG_DIR, safe_log_name
from ..system import find_claude, find_python
from ..widgets import (AdaptiveBox, FlowLayout, Icon, NeonProgress, PulseDot, Spinner, badge, card, icon_button, label,
                       set_button_enabled)
from .common import PLATFORM_LABEL, Page, open_file, open_folder


class StepRow(QWidget):
    def __init__(self, n: int, text: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(4, 7, 4, 7)
        h.setSpacing(12)
        self.holder = QStackedLayout()
        w = QWidget()
        w.setFixedSize(26, 26)
        w.setLayout(self.holder)
        self.num = label(str(n))
        self.num.setAlignment(Qt.AlignCenter)
        self.icon = Icon("check", 13, T.GREEN)
        self.spin = Spinner(20, T.PINK)
        sw = QWidget()
        sl = QHBoxLayout(sw)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.addWidget(self.spin)
        for x in (self.num, self.icon, sw):
            self.holder.addWidget(x)
        h.addWidget(w)
        self.text = label(text)
        h.addWidget(self.text, 1)
        self.time = label("", "Dim")
        h.addWidget(self.time)
        self.t0 = None
        self.set_state("pending")

    def set_state(self, st: str):
        self.state = st
        if st == "pending":
            self.holder.setCurrentIndex(0)
            self.num.setStyleSheet(f"color: {T.DIM}; border: 1px solid {T.BORDER}; border-radius: 13px;"
                                   " font-size: 11px; font-weight: 700;")
            self.text.setStyleSheet(f"color: {T.MUTED};")
        elif st == "active":
            self.holder.setCurrentIndex(2)
            self.text.setStyleSheet(f"color: {T.TEXT}; font-weight: 700;")
            self.t0 = time.time()
        elif st in ("done", "skipped"):
            self.holder.setCurrentIndex(1)
            self.icon.set("check" if st == "done" else "dash", T.GREEN if st == "done" else T.DIM)
            self.text.setStyleSheet(f"color: {T.TEXT if st == 'done' else T.DIM};")
            if st == "skipped":
                self.time.setText("não se aplica")
        elif st in ("error", "cancel"):
            self.holder.setCurrentIndex(1)
            self.icon.set("error" if st == "error" else "stop", T.RED if st == "error" else T.AMBER)
            self.text.setStyleSheet(f"color: {T.RED if st == 'error' else T.AMBER}; font-weight: 700;")
        if st in ("done", "error", "cancel") and self.t0:
            self.tick()
            self.t0 = None

    def tick(self):
        if self.t0:
            s = int(time.time() - self.t0)
            self.time.setText(f"{s // 60}:{s % 60:02d}")


LOG_COLORS = {"info": T.CYAN, "cmd": T.ORANGE, "output": "#bdb0d0", "claude": "#ff8cc6", "error": T.RED,
              "result": T.GREEN, "raw": T.DIM}
LOG_PREFIX = {"info": "●", "cmd": "▶", "output": " ", "claude": "◆", "error": "✖", "result": "✔", "raw": "·"}


class Processing(Page):
    finished = Signal(str, dict)

    def __init__(self, state):
        super().__init__("Processamento", "Nenhum processamento em andamento")
        self.state = state
        self.runner: JobRunner | None = None
        self.job: dict | None = None
        self.cur = -1
        self.progress_val = 0.0
        self.t_start = 0.0
        self.log_path: Path | None = None

        self.stack = QStackedLayout()
        holder = QWidget()
        holder.setLayout(self.stack)
        self.body.addWidget(holder, 1)

        # vazio
        empty = QWidget()
        ev = QVBoxLayout(empty)
        ev.addStretch(1)
        ic = Icon("sync", 46, T.DIM)
        ic.setFixedSize(80, 80)
        ev.addWidget(ic, 0, Qt.AlignHCenter)
        ev.addWidget(label("Nada rodando agora", "SectionTitle"), 0, Qt.AlignHCenter)
        hint = label("Comece um corte e acompanhe aqui cada etapa e os logs em tempo real.", "Muted", wrap=True)
        hint.setAlignment(Qt.AlignCenter)
        ev.addWidget(hint)
        go = icon_button("NOVO CORTE", "add", "Primary")
        go.setFixedWidth(200)
        go.clicked.connect(lambda: state.navigate.emit("new"))
        ev.addSpacing(10)
        ev.addWidget(go, 0, Qt.AlignHCenter)
        ev.addStretch(2)
        self.stack.addWidget(empty)

        # rodando
        run = QWidget()
        rv = QVBoxLayout(run)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(14)
        top = card("CardFlat")
        tv = QVBoxLayout(top)
        tv.setContentsMargins(22, 18, 22, 18)
        tv.setSpacing(10)
        th = QHBoxLayout()
        self.dot = PulseDot(T.PINK, 12)
        th.addWidget(self.dot)
        tt = QVBoxLayout()
        tt.setSpacing(0)
        self.status_lbl = label("Processando", "SectionTitle")
        self.status_lbl.setStyleSheet("font-size: 17px; font-weight: 800;")
        self.step_lbl = label("", "Muted", wrap=True)
        tt.addWidget(self.status_lbl)
        tt.addWidget(self.step_lbl)
        th.addLayout(tt, 1)
        self.plat_badge = badge("", T.PURPLE)
        th.addWidget(self.plat_badge)
        self.elapsed = label("0:00", "Muted")
        self.elapsed.setStyleSheet(f"color: {T.MUTED}; font-size: 20px; font-weight: 700;"
                                   " font-family: Cascadia Mono, Consolas;")
        th.addSpacing(10)
        th.addWidget(self.elapsed)
        tv.addLayout(th)
        ph = QHBoxLayout()
        self.bar = NeonProgress()
        ph.addWidget(self.bar, 1)
        self.pct = label("0%")
        self.pct.setFixedWidth(52)
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pct.setStyleSheet("font-weight: 800; font-size: 15px;")
        ph.addWidget(self.pct)
        tv.addLayout(ph)
        self.url_lbl = label("", "Dim", wrap=True)
        self.url_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        tv.addWidget(self.url_lbl)
        btns_w = QWidget()
        btns = FlowLayout(btns_w, 8)
        self.b_folder = icon_button("Abrir pasta", "folder", "Ghost")
        self.b_folder.clicked.connect(self._open_out)
        self.b_lib = icon_button("Ver na biblioteca", "library", "Ghost")
        self.b_lib.clicked.connect(lambda: state.navigate.emit("library"))
        self.b_new = icon_button("Novo corte", "add", "Ghost")
        self.b_new.clicked.connect(lambda: state.navigate.emit("new"))
        self.b_cancel = icon_button("CANCELAR", "cancel", "Danger")
        self.b_cancel.clicked.connect(self._ask_cancel)
        for b in (self.b_folder, self.b_lib, self.b_new, self.b_cancel):
            btns.addWidget(b)
        tv.addWidget(btns_w)
        rv.addWidget(top)

        mid_w = AdaptiveBox(900, 14)
        mid = mid_w.box
        steps = card("CardFlat")
        steps.setFixedWidth(330)

        def _stack(vertical: bool):  # janela estreita: etapas em cima, log embaixo
            if vertical:
                steps.setMinimumWidth(0)
                steps.setMaximumWidth(16777215)
            else:
                steps.setFixedWidth(330)
        mid_w.on_change = _stack
        sv = QVBoxLayout(steps)
        sv.setContentsMargins(18, 16, 18, 16)
        sv.addWidget(label("Etapas", "SectionTitle"))
        sv.addSpacing(4)
        self.rows: list[StepRow] = []
        for i, s in enumerate(STEPS):
            r = StepRow(i + 1, s.label)
            self.rows.append(r)
            sv.addWidget(r)
        sv.addStretch(1)
        self.result_box = QTextBrowser()
        self.result_box.setObjectName("Post")
        self.result_box.setOpenExternalLinks(False)
        self.result_box.setMaximumHeight(0)
        mid.addWidget(steps)

        logc = card("CardFlat")
        lv = QVBoxLayout(logc)
        lv.setContentsMargins(18, 16, 18, 16)
        lh = QHBoxLayout()
        lh.addWidget(label("Logs em tempo real", "SectionTitle"))
        lh.addStretch(1)
        self.verbose = QCheckBox("Saída completa dos scripts")
        self.verbose.setChecked(True)
        lh.addWidget(self.verbose)
        cp = icon_button("", "copy", "Ghost", "Copiar log")
        cp.setFixedWidth(40)
        cp.clicked.connect(self._copy_log)
        lh.addWidget(cp)
        of = icon_button("", "doc", "Ghost", "Abrir arquivo de log")
        of.setFixedWidth(40)
        of.clicked.connect(lambda: self.log_path and open_file(self.log_path))
        lh.addWidget(of)
        lv.addLayout(lh)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(6000)
        self.log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.log.setMinimumHeight(260)
        lv.addWidget(self.log, 1)
        lv.addWidget(self.result_box)
        mid.addWidget(logc, 1)
        rv.addWidget(mid_w, 1)
        self.stack.addWidget(run)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ início
    def start(self, job: dict) -> bool:
        claude = find_claude(self.state.settings["claude_path"])
        if not claude:
            QMessageBox.warning(self, "Claude Code não encontrado",
                                "Não achei o Claude Code. Instale com:\n\nirm https://claude.ai/install.ps1 | iex\n\n"
                                "ou indique o caminho em Configurações.")
            return False
        out = self.state.settings.out_dir(job["platform"])
        try:
            # --add-dir de pasta inexistente é ignorado e aí ler/escrever no job pede aprovação (que ninguém dá).
            # Criar a pasta não apaga nem altera nada que já exista.
            out.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            QMessageBox.warning(self, "Pasta de saída", f"Não consegui criar a pasta de saída:\n{out}\n\n{e}")
            return False
        try:
            argv, prompt = build_command(claude, job["url"], job["platform"], job["clips"], out,
                                         job.get("lang", AUTO_LANG), job.get("original_captions", False),
                                     job.get("zoom", True), job.get("cover", True))
        except ValueError as e:
            QMessageBox.warning(self, "Pasta inválida", str(e))
            return False
        self.job = dict(job, prompt=prompt, out=str(out))
        self.log_path = LOG_DIR / safe_log_name(job["platform"])
        py = find_python()
        self.runner = JobRunner(argv, self.log_path, str(Path(py).parent) if py else None, prompt, self)
        self.runner.event.connect(self._on_event)
        self.runner.finished.connect(self._on_finished)

        sub = f"Rodando {prompt.split()[0]} · {job['clips']} corte(s)"
        sub += f" · idioma: {LANGS.get(job.get('lang', AUTO_LANG), 'Detectar').lower()}"
        if job.get("original_captions") and job.get("lang") != "pt":
            sub += " · legenda original"
        self.subtitle.setText(sub)
        self.url_lbl.setText(job["url"])
        plat = job["platform"]
        self.plat_badge.setText(PLATFORM_LABEL[plat].upper())
        self.plat_badge.setStyleSheet(badge("", "#ff4e45" if plat != TWITCH else T.PURPLE).styleSheet())
        self.log.clear()
        self.result_box.setMaximumHeight(0)
        self.result_box.clear()
        for i, r in enumerate(self.rows):
            r.time.setText("")
            r.t0 = None
            r.set_state("pending")
            r.setVisible(True)
        self.cur = -1
        self.progress_val = 0
        self.bar.state = "run"
        self.bar.active = True
        self.bar.set_value(0)
        self.pct.setText("0%")
        self.dot.set_color(T.PINK, True)
        self.status_lbl.setText("Processando…")
        for b in (self.b_lib, self.b_new):
            b.setVisible(False)
        set_button_enabled(self.b_cancel, True)
        self.b_cancel.setVisible(True)
        self.stack.setCurrentIndex(1)
        self.t_start = time.time()
        self.timer.start(1000)
        self._append(Event("info", f"Comando: claude -p \"{prompt}\" (mesmas permissões do rodar_automatico.ps1)"))
        self._append(Event("info", f"Log salvo em {self.log_path}"))
        self._set_step(0)
        self.runner.start()
        return True

    # ------------------------------------------------------------ eventos
    def _on_event(self, ev: Event):
        if ev.step and ev.step in STEP_INDEX:
            self._set_step(STEP_INDEX[ev.step])
        if ev.kind == "result":
            return  # mostrado no fim
        if ev.kind == "lang":
            self._on_language(ev.data)
            return
        if ev.kind in ("output", "raw") and not self.verbose.isChecked():
            return
        self._append(ev)

    def _on_language(self, data: dict):
        job = self.job or {}
        if data.get("translated"):
            self._append(Event("info", f"Legenda traduzida para {lang_name(data['translated'])} (pt-BR) no render."))
            return
        code = data.get("lang", "")
        if not code or code == job.get("detected_lang"):
            return
        job["detected_lang"] = code
        chosen = job.get("lang", AUTO_LANG)
        if code == "pt":
            msg = "Idioma do vídeo: português. A legenda sai em português, sem tradução."
        elif job.get("original_captions"):
            msg = f"Idioma do vídeo: {lang_name(code)}. A legenda fica em {lang_name(code)} (sem tradução, como pedido)."
        else:
            msg = f"Idioma do vídeo: {lang_name(code)}. A legenda vai ser traduzida para português (pt-BR)."
        self._append(Event("info", msg))
        if chosen != AUTO_LANG and chosen != code:
            self._append(Event("error", f"Atenção: você escolheu {lang_name(chosen)}, mas a transcrição saiu em "
                                        f"{lang_name(code)}. Confira a legenda dos clipes."))

    def _append(self, ev: Event):
        col = LOG_COLORS.get(ev.kind, T.TEXT)
        ts = time.strftime("%H:%M:%S")
        pre = LOG_PREFIX.get(ev.kind, " ")
        text = html.escape(ev.text).replace("\n", "<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;")
        weight = "font-weight:600;" if ev.kind in ("cmd", "claude", "error") else ""
        self.log.appendHtml(f'<span style="color:{T.DIM}">{ts}</span> '
                            f'<span style="color:{col};{weight}">{pre} {text}</span>')
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_step(self, idx: int):
        if idx <= self.cur:
            return
        for i in range(max(self.cur, 0), idx):
            if self.rows[i].state == "active":
                self.rows[i].set_state("done")
            elif self.rows[i].state == "pending" and self.rows[i].isVisible():
                self.rows[i].set_state("skipped" if STEPS[i].key == "translate" else "done")
        self.cur = idx
        self.rows[idx].set_state("active")
        self.step_lbl.setText(f"Etapa {idx + 1}/{len(STEPS)} · {STEPS[idx].label}")
        self.progress_val = max(self.progress_val, STEPS[idx].start)
        self._show_progress()

    def _show_progress(self):
        self.bar.animate_to(self.progress_val)
        self.pct.setText(f"{int(self.progress_val)}%")

    def _tick(self):
        s = int(time.time() - self.t_start)
        h, rem = divmod(s, 3600)
        self.elapsed.setText(f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60}:{rem % 60:02d}")
        if self.cur >= 0:
            self.rows[self.cur].tick()
            st = STEPS[self.cur]
            # avança devagar dentro da etapa (estimativa), sem passar do teto dela
            self.progress_val += (st.end - self.progress_val) * 0.015
            self._show_progress()

    # ------------------------------------------------------------ cancelar / fim
    def is_running(self) -> bool:
        return bool(self.runner and self.runner.running())

    def _ask_cancel(self):
        if not self.is_running():
            return
        r = QMessageBox.question(
            self, "Cancelar processamento",
            "Encerrar o processamento agora?\n\nO Claude Code e os scripts serão encerrados. Nenhum arquivo é "
            "apagado: o que já foi baixado e transcrito continua na pasta do job.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r == QMessageBox.Yes:
            self.cancel()

    def cancel(self):
        if self.runner:
            set_button_enabled(self.b_cancel, False)
            self.status_lbl.setText("Cancelando…")
            self.runner.cancel()

    def _on_finished(self, status: str, data: dict):
        self.timer.stop()
        self._tick()
        self.bar.active = False
        if self.cur >= 0:
            row = self.rows[self.cur]
        else:
            row = None
        if status == "ok":
            for r in self.rows:
                if r.state == "active":
                    r.set_state("done")
                elif r.state == "pending" and r.isVisible():
                    r.set_state("skipped" if r is self.rows[STEP_INDEX["translate"]] else "done")
            self.progress_val = 100
            self.bar.state = "ok"
            self.status_lbl.setText("Concluído")
            self.dot.set_color(T.GREEN, False)
            self.step_lbl.setText("Confira cada clipe antes de postar. Nada foi publicado.")
        elif status == "cancelado":
            if row:
                row.set_state("cancel")
            self.bar.state = "cancel"
            self.status_lbl.setText("Cancelado")
            self.dot.set_color(T.AMBER, False)
            self.step_lbl.setText("Processamento cancelado. Nenhum arquivo foi apagado.")
            self._append(Event("info", "Processamento cancelado pelo usuário."))
        else:
            if row:
                row.set_state("error")
            self.bar.state = "error"
            self.status_lbl.setText("Erro no processamento")
            self.dot.set_color(T.RED, False)
            self.step_lbl.setText(data.get("error") or "Veja os detalhes no log e na resposta do Claude abaixo.")
            if data.get("error"):
                self._append(Event("error", data["error"]))
        self.bar.update()
        self._show_progress()
        result = data.get("result", "")
        if result:
            self.result_box.setMarkdown(result)
            self.result_box.setMaximumHeight(260)
            self._append(Event("result", "Resposta final do Claude exibida abaixo."))
        self.b_cancel.setVisible(False)
        for b in (self.b_lib, self.b_new):
            b.setVisible(True)
        self.subtitle.setText(f"Último processamento: {status}")
        job = dict(self.job or {}, status=status, elapsed=round(data.get("elapsed", 0)),
                   log=str(self.log_path) if self.log_path else "", result=result[:4000])
        self.finished.emit(status, job)

    def _open_out(self):
        if self.job:
            open_folder(Path(self.job["out"]))

    def _copy_log(self):
        QGuiApplication.clipboard().setText(self.log.toPlainText())
        self.state.toast.emit("Log copiado.", "info")
