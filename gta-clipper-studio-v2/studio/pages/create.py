"""Criar cortes: formulário (estilo Cobalt), processamento na mesma página e cortes recentes."""
from __future__ import annotations

import html
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QHBoxLayout, QPlainTextEdit, QStackedWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from .. import theme as T
from ..core import AUTH_REQUIRED_MESSAGE, LEGENDAS, MAX_CLIPS, STEP_INDEX, STEPS, YOUTUBE, Event, build_command, \
    detect_platform, validate_link
from ..runner import JobRunner
from ..storage import LOG_DIR, safe_log_name
from ..system import find_agent, find_python, AGENTS
from ..codex_agent import build_codex_command
from ..widgets import (AdaptiveStack, AppMark, Badge, Collapsible, EmptyState, Icon, LinkField, SectionHeader,
                       Select, Spinner, StepProgress, VideoCard, button, clear_layout, divider, elide, label, panel)
from .common import PLATFORM_COLOR, PLATFORM_LABEL, Page, clip_meta, open_file, open_folder, sync_info

LOG_COLORS = {"info": T.INFO, "cmd": T.SECONDARY, "output": T.MUTED, "claude": T.PRIMARY, "agent": T.PRIMARY, "error": T.ERROR,
              "result": T.SUCCESS, "raw": T.DIM}
LOG_PREFIX = {"info": "●", "cmd": "▶", "output": " ", "claude": "◆", "agent": "◆", "error": "✖", "result": "✔", "raw": "·"}


def _fmt_secs(s: int) -> str:
    h, rem = divmod(int(s), 3600)
    return f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60}:{rem % 60:02d}"


class StepRow(QWidget):
    """Linha de etapa: ícone de estado, nome e tempo gasto."""

    def __init__(self, text: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 3, 0, 3)
        h.setSpacing(T.SP2)
        self.holder = QStackedWidget()
        self.holder.setFixedSize(20, 20)
        self.dot = QFrame()
        self.dot.setFixedSize(20, 20)
        self.ic = Icon("check", 11, T.SUCCESS)
        self.spin = Spinner(14)
        sp = QWidget()
        sl = QHBoxLayout(sp)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.addWidget(self.spin)
        for w in (self.dot, self.ic, sp):
            self.holder.addWidget(w)
        h.addWidget(self.holder)
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
            self.dot.setStyleSheet(f"QFrame {{ border: 1px solid {T.BORDER_STRONG}; border-radius: 10px; margin: 5px; }}")
            self.text.setStyleSheet(f"color: {T.DIM};")
        elif st == "active":
            self.holder.setCurrentIndex(2)
            self.text.setStyleSheet(f"color: {T.TEXT}; font-weight: 600;")
            self.t0 = time.time()
        elif st in ("done", "skipped"):
            self.holder.setCurrentIndex(1)
            self.ic.set("check" if st == "done" else "dash", T.SUCCESS if st == "done" else T.DIM)
            self.text.setStyleSheet(f"color: {T.MUTED if st == 'done' else T.DIM};")
        elif st in ("error", "cancel"):
            self.holder.setCurrentIndex(1)
            self.ic.set("error" if st == "error" else "stop", T.ERROR if st == "error" else T.WARNING)
            self.text.setStyleSheet(f"color: {T.ERROR if st == 'error' else T.WARNING}; font-weight: 600;")
        if st in ("done", "error", "cancel") and self.t0:
            self.tick()
            self.t0 = None

    def tick(self):
        if self.t0:
            self.time.setText(_fmt_secs(time.time() - self.t0))


class CreatePage(Page):
    finished = Signal(str, dict)

    def __init__(self, state):
        super().__init__(max_width=T.CONTENT_MAX_W)
        self.state = state
        self.runner: JobRunner | None = None
        self.job: dict | None = None
        self.pending_start = False
        self.preserve_form_on_return = False
        self.cur = -1
        self.t_start = 0.0
        self.log_path: Path | None = None
        self._cancel_armed = False

        self.stack = AdaptiveStack()
        self.stack.addWidget(self._build_form())
        self.stack.addWidget(self._build_run())
        self.body.addWidget(self.stack)
        self.body.addSpacing(T.SP4)

        # cortes recentes
        self.recent_box = QWidget()
        rv = QVBoxLayout(self.recent_box)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(T.SP4)
        lib = button("Ver biblioteca", "library", "Ghost")
        lib.clicked.connect(lambda: state.navigate.emit("library"))
        rv.addWidget(SectionHeader("Cortes recentes", right=lib))
        self.recent_row = QHBoxLayout()
        self.recent_row.setSpacing(T.SP4)
        rv.addLayout(self.recent_row)
        self.body.addWidget(self.recent_box)
        self.body.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.cancel_timer = QTimer(self)
        self.cancel_timer.setSingleShot(True)
        self.cancel_timer.timeout.connect(self._disarm_cancel)
        self._recent_timer = QTimer(self)
        self._recent_timer.setSingleShot(True)
        self._recent_timer.timeout.connect(self._render_recent)
        state.clips_changed.connect(self._render_recent)
        state.checks_changed.connect(self._render_deps)
        state.auth_changed.connect(self._on_auth_changed)
        state.default_lang_changed.connect(self.lang.set_key)
        self._on_url("")

    # ================================================================ formulário
    def _build_form(self) -> QWidget:
        w = QWidget()
        outer = QHBoxLayout(w)
        outer.setContentsMargins(0, T.SP8, 0, 0)
        form = QWidget()
        form.setMaximumWidth(T.FORM_MAX_W)
        v = QVBoxLayout(form)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(T.SP4)
        mark = AppMark(48)
        v.addWidget(mark, 0, Qt.AlignHCenter)
        v.addSpacing(T.SP2)
        hero = label("Transforme lives em clipes.", "Hero")
        hero.setAlignment(Qt.AlignCenter)
        v.addWidget(hero)
        sub = label("Os melhores momentos, automaticamente.", "HeroSub")
        sub.setAlignment(Qt.AlignCenter)
        v.addWidget(sub)
        v.addSpacing(T.SP4)

        self.link = LinkField("Cole o link do vídeo ou da live")
        self.link.edit.textChanged.connect(self._on_url)
        self.link.submitted.connect(self._start)
        self.link.paste.clicked.connect(self._paste)
        v.addWidget(self.link)
        hint = QHBoxLayout()
        hint.setContentsMargins(T.SP1, 0, 0, 0)
        hint.setSpacing(T.SP1)
        self.hint_ic = Icon("info", 11, T.DIM)
        self.hint = label("", "Dim")
        hint.addWidget(self.hint_ic)
        hint.addWidget(self.hint, 1)
        v.addLayout(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(T.SP4)
        grid.setVerticalSpacing(T.SP1 + 2)
        grid.addWidget(label("Quantidade de cortes", "Label"), 0, 0)
        grid.addWidget(label("Idioma da legenda", "Label"), 0, 1)
        self.count = Select()
        self.lang = Select([(k, v_) for k, v_ in LEGENDAS.items()])
        self.lang.set_key("pt")
        grid.addWidget(self.count, 1, 0)
        grid.addWidget(self.lang, 1, 1)
        v.addLayout(grid)

        self.dep_banner = QFrame()
        self.dep_banner.setObjectName("PanelFlat")
        self.dep_banner.setStyleSheet(f"#PanelFlat {{ border-color: {T.rgba(T.WARNING, 0.4)}; }}")
        db = QHBoxLayout(self.dep_banner)
        db.setContentsMargins(T.SP3, T.SP2, T.SP2, T.SP2)
        db.addWidget(Icon("warn", 13, T.WARNING))
        self.dep_text = label("", wrap=True)
        db.addWidget(self.dep_text, 1)
        go = button("Configurações", None, "Ghost")
        go.clicked.connect(lambda: self.state.navigate.emit("settings"))
        db.addWidget(go)
        self.dep_banner.hide()
        v.addWidget(self.dep_banner)

        self.start_btn = button("Gerar clipes", "sparkle", "Primary", large=True)
        self.start_btn.clicked.connect(self._start)
        v.addWidget(self.start_btn)
        note = label("Nada é publicado automaticamente. Os clipes ficam só no seu computador.", "Dim")
        note.setAlignment(Qt.AlignCenter)
        v.addWidget(note)
        outer.addStretch(1)
        outer.addWidget(form, 100)
        outer.addStretch(1)
        return w

    def platform_for_link(self) -> str:
        return detect_platform(self.link.edit.text().strip()) or YOUTUBE

    def _paste(self):
        self.link.edit.setText(QGuiApplication.clipboard().text().strip())
        self.link.edit.setFocus()

    def _fill_counts(self):
        plat = self.platform_for_link()
        mx = MAX_CLIPS[plat]
        cur = self.count.key() or int(self.state.settings["last_clips"] or 3)
        self.count.blockSignals(True)
        self.count.clear()
        for n in range(1, mx + 1):
            self.count.addItem(f"{n} {'clipe' if n == 1 else 'clipes'}", n)
        self.count.set_key(min(int(cur), mx))
        self.count.blockSignals(False)

    def _on_url(self, text: str):
        text = (text or "").strip()
        found = detect_platform(text)
        plat = self.platform_for_link()
        self._fill_counts()
        if found:
            self.link.platform.set("YouTube" if found == YOUTUBE else "Twitch", PLATFORM_COLOR[found])
            self.link.platform.show()
        else:
            self.link.platform.hide()
        ok, msg = validate_link(text, plat) if text else (False, "")
        if not text:
            self.hint_ic.set("info", T.DIM)
            self.hint.setText("Vídeos do YouTube (qualquer duração) e VODs da Twitch.")
            self.link.set_state("")
        elif ok:
            self.hint_ic.set("check", T.SUCCESS)
            kind = "vídeo do YouTube" if plat == YOUTUBE else "live"
            self.hint.setText(f"Pronto para cortar como {kind}.")
            self.link.set_state("")
        else:
            self.hint_ic.set("warn", T.ERROR)
            self.hint.setText(msg)
            self.link.set_state("error")
        self._update_start()

    def _missing_deps(self) -> list[str]:
        return [c.name for c in self.state.checks if c.required and not c.ok]

    def _render_deps(self):
        miss = self._missing_deps()
        claude_ok = bool(find_agent(self.state.settings["agent"], self.state.settings.agent_path))
        auth_status = self.state.auth_status
        if auth_status == "disconnected":
            self.dep_text.setText("Agente selecionado está desconectado. Abra Configurações e clique em Autenticar.")
        elif auth_status == "auth_error":
            self.dep_text.setText("O agente selecionado recusou a autenticação. Verifique novamente em Configurações.")
        elif auth_status == "unavailable" or not claude_ok:
            self.dep_text.setText("Agente selecionado não encontrado. Sem ele não dá para gerar clipes.")
        elif miss:
            self.dep_text.setText(f"Dependência ausente: {', '.join(miss[:3])}"
                                  + (f" e mais {len(miss) - 3}" if len(miss) > 3 else "") + ".")
        elif self.state.checking and not self.state.checks:
            self.dep_banner.hide()
            self._update_start()
            return
        self.dep_banner.setVisible(auth_status in ("disconnected", "auth_error", "unavailable")
                                   or not claude_ok or bool(miss))
        self._update_start()

    def _update_start(self):
        text = self.link.edit.text().strip()
        ok = bool(text) and validate_link(text, self.platform_for_link())[0]
        running = self.state.job_running
        checking = self.state.auth_status == "checking" or self.pending_start
        self.start_btn.setEnabled(ok and not running and not checking)
        if running:
            self.start_btn.setToolTip("Já existe um processamento em andamento.")
        elif checking:
            self.start_btn.setToolTip("Verificando a autenticação do agente selecionado.")
        elif self.state.auth_status != "connected":
            self.start_btn.setToolTip("A autenticação será verificada antes de gerar os clipes.")
        else:
            self.start_btn.setToolTip("")

    def _start(self):
        if self.state.job_running:
            self.state.toast.emit("Já existe um processamento em andamento.", "warn")
            return
        if self.pending_start:
            return
        url = self.link.edit.text().strip()
        plat = self.platform_for_link()
        ok, msg = validate_link(url, plat)
        if not ok:
            self.link.set_state("error")
            self.hint.setText(msg or "Cole um link válido.")
            return
        self.pending_start = True
        self._update_start()
        self.state.refresh_auth_status()

    def _on_auth_changed(self):
        self._render_deps()
        if self.pending_start and self.state.auth_status != "checking":
            self.pending_start = False
            if self.state.auth_status == "connected":
                self._submit_form()
            else:
                self.state.toast.emit(self._auth_block_message(), "error")
        self._update_start()

    def _auth_block_message(self) -> str:
        messages = {
            "disconnected": AUTH_REQUIRED_MESSAGE,
            "unavailable": "Agente selecionado não está disponível. Configure ou instale o agente selecionado em Configurações.",
            "auth_error": "Não foi possível confirmar a autenticação do agente selecionado. Verifique em Configurações.",
        }
        return messages.get(self.state.auth_status, "A autenticação do agente selecionado ainda está sendo verificada.")

    def _submit_form(self):
        url = self.link.edit.text().strip()
        plat = self.platform_for_link()
        ok, msg = validate_link(url, plat)
        if not ok:
            self.link.set_state("error")
            self.hint.setText(msg or "Cole um link válido.")
            return
        n = int(self.count.key() or 1)
        lang = self.lang.key() or "pt"
        s = self.state.settings
        s["last_platform"], s["last_clips"] = plat, n
        s.save()
        self.state.job_started.emit({"url": url, "platform": plat, "clips": n, "legenda": lang})

    # ================================================================ processamento
    def _build_run(self) -> QWidget:
        w = QWidget()
        outer = QHBoxLayout(w)
        outer.setContentsMargins(0, T.SP4, 0, 0)
        col = QWidget()
        col.setMaximumWidth(760)
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(T.SP4)

        top = QHBoxLayout()
        top.setSpacing(T.SP2)
        self.r_plat = Badge("", T.MUTED)
        top.addWidget(self.r_plat)
        self.r_url = label("", "Dim")
        self.r_url.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top.addWidget(self.r_url, 1)
        self.r_elapsed = label("0:00", "Mono")
        self.r_elapsed.setStyleSheet(f"font-size: {T.FS_LG}px; color: {T.TEXT};")
        top.addWidget(self.r_elapsed)
        v.addLayout(top)

        self.r_title = label("Processando", "H1")
        v.addWidget(self.r_title)
        self.r_step = label("", "Muted")
        v.addWidget(self.r_step)
        self.bar = StepProgress(len(STEPS))
        v.addWidget(self.bar)

        steps = panel("Panel")
        sv = QVBoxLayout(steps)
        sv.setContentsMargins(T.SP4, T.SP3, T.SP4, T.SP3)
        sv.setSpacing(0)
        self.rows: list[StepRow] = []
        for s in STEPS:
            r = StepRow(s.label)
            self.rows.append(r)
            sv.addWidget(r)
        v.addWidget(steps)

        acts = QHBoxLayout()
        acts.setSpacing(T.SP2)
        self.b_cancel = button("Cancelar", "cancel", "Danger")
        self.b_cancel.clicked.connect(self._cancel_clicked)
        self.b_new = button("Novo corte", "add", "Primary")
        self.b_new.clicked.connect(self._new_cut)
        self.b_folder = button("Abrir pasta", "folder")
        self.b_folder.clicked.connect(self._open_out)
        self.b_lib = button("Ver na biblioteca", "library", "Ghost")
        self.b_lib.clicked.connect(lambda: self.state.navigate.emit("library"))
        for b in (self.b_cancel, self.b_new, self.b_folder, self.b_lib):
            acts.addWidget(b)
        acts.addStretch(1)
        v.addLayout(acts)

        # resultado
        self.result_box = QWidget()
        rb = QVBoxLayout(self.result_box)
        rb.setContentsMargins(0, T.SP2, 0, 0)
        rb.setSpacing(T.SP3)
        self.result_title = label("Clipes gerados", "H2")
        rb.addWidget(self.result_title)
        self.result_row = QHBoxLayout()
        self.result_row.setSpacing(T.SP4)
        rb.addLayout(self.result_row)
        self.result_empty = EmptyState("video", "Nenhum clipe novo",
                                       "Nenhum momento passou da nota mínima, ou o processamento parou antes de "
                                       "renderizar. Veja a resposta do agente.", compact=True)
        rb.addWidget(self.result_empty)
        self.answer = QTextBrowser()
        self.answer.setObjectName("Prose")
        self.answer.setOpenExternalLinks(False)
        self.answer.setMinimumHeight(160)
        self.answer_sec = Collapsible("Resposta do agente", self.answer, expanded=False)
        rb.addWidget(self.answer_sec)
        v.addWidget(self.result_box)

        # logs
        logw = QWidget()
        lv = QVBoxLayout(logw)
        lv.setContentsMargins(0, 0, 0, 0)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(6000)
        self.log.setMinimumHeight(260)
        lv.addWidget(self.log)
        tools = QWidget()
        th = QHBoxLayout(tools)
        th.setContentsMargins(0, 0, 0, 0)
        th.setSpacing(T.SP1)
        self.verbose = QCheckBox("Saída completa")
        self.verbose.setChecked(True)
        th.addWidget(self.verbose)
        cp = button("", "copy", "Ghost", "Copiar log")
        cp.clicked.connect(self._copy_log)
        th.addWidget(cp)
        of = button("", "doc", "Ghost", "Abrir arquivo de log")
        of.clicked.connect(lambda: self.log_path and open_file(self.log_path))
        th.addWidget(of)
        self.logs = Collapsible("Logs técnicos", logw, expanded=False, right=tools)
        v.addWidget(divider())
        v.addWidget(self.logs)

        outer.addStretch(1)
        outer.addWidget(col, 100)
        outer.addStretch(1)
        return w

    def is_running(self) -> bool:
        return bool(self.runner and self.runner.running())

    def start(self, job: dict) -> bool:
        agent = self.state.settings["agent"]
        claude = find_agent(agent, self.state.settings.agent_path)
        if not claude:
            self._render_deps()
            self.state.toast.emit("Agente selecionado não encontrado. Veja Configurações.", "error")
            return False
        out = self.state.settings.out_dir(job["platform"])
        try:
            # --add-dir de pasta inexistente é ignorado e aí ler/escrever no job pede aprovação (que ninguém dá).
            # Criar a pasta não apaga nem altera nada que já exista.
            out.mkdir(parents=True, exist_ok=True)
            builder = build_codex_command if agent == "codex" else build_command
            argv, prompt = builder(claude, job["url"], job["platform"], job["clips"], out, job.get("legenda"))
        except (OSError, ValueError) as e:
            self.state.toast.emit(f"Não deu para iniciar: {e}", "error")
            return False
        self.job = dict(job, prompt=prompt, out=str(out), agent=agent)
        self.log_path = LOG_DIR / safe_log_name(job["platform"])
        py = find_python()
        self.runner = JobRunner(argv, self.log_path, str(Path(py).parent) if py else None, prompt, self,
                                agent=agent, out_dir=out)
        self.runner.event.connect(self._on_event)
        self.runner.finished.connect(self._on_finished)

        plat = job["platform"]
        self.r_plat.set(PLATFORM_LABEL[plat], PLATFORM_COLOR[plat])
        elide(self.r_url, job["url"], 520, Qt.ElideMiddle)
        self.r_title.setText("Processando")
        self.log.clear()
        self.answer.clear()
        self.result_box.hide()
        for r in self.rows:
            r.time.setText("")
            r.t0 = None
            r.set_state("pending")
        self.cur = -1
        self.bar.reset(len(STEPS))
        self._disarm_cancel()
        self.b_cancel.setEnabled(True)
        self.b_cancel.show()
        for b in (self.b_new, self.b_folder, self.b_lib):
            b.hide()
        self.stack.setCurrentIndex(1)
        self.recent_box.hide()
        self.t_start = time.time()
        self.timer.start(1000)
        self._append(Event("info", f"Agente: {AGENTS[agent]} · {job['url']}"))
        self._append(Event("info", f"Log salvo em {self.log_path}"))
        self._set_step(0)
        self.runner.start()
        return True

    def _on_event(self, ev: Event):
        if ev.data.get("auth_error"):
            self.state.set_auth_status("auth_error", AUTH_REQUIRED_MESSAGE)
        if ev.step and ev.step in STEP_INDEX:
            self._set_step(STEP_INDEX[ev.step])
        if ev.kind == "result":
            return
        if ev.kind in ("output", "raw") and not self.verbose.isChecked():
            return
        self._append(ev)

    def _append(self, ev: Event):
        col = LOG_COLORS.get(ev.kind, T.TEXT)
        ts = time.strftime("%H:%M:%S")
        text = html.escape(ev.text).replace("\n", "<br>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;")
        self.log.appendHtml(f'<span style="color:{T.DIM}">{ts}</span> '
                            f'<span style="color:{col}">{LOG_PREFIX.get(ev.kind, " ")} {text}</span>')
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_step(self, idx: int):
        if idx <= self.cur:
            return
        for i in range(max(self.cur, 0), idx):
            if self.rows[i].state == "active":
                self.rows[i].set_state("done")
                self.bar.done.add(i)
            elif self.rows[i].state == "pending":
                self.rows[i].set_state("skipped")
                self.bar.skipped.add(i)
        self.cur = idx
        self.rows[idx].set_state("active")
        self.bar.set_active(idx)
        self.r_step.setText(f"Etapa {idx + 1} de {len(STEPS)} · {STEPS[idx].label}")
        self.state.job_progress.emit(STEPS[idx].label)

    def _tick(self):
        self.r_elapsed.setText(_fmt_secs(time.time() - self.t_start))
        if self.cur >= 0:
            self.rows[self.cur].tick()

    # cancelamento com confirmação no próprio botão (sem diálogo)
    def _cancel_clicked(self):
        if not self.is_running():
            return
        if not self._cancel_armed:
            self._cancel_armed = True
            self.b_cancel.setText("Confirmar cancelamento")
            self.cancel_timer.start(4000)
            return
        self.cancel()

    def _disarm_cancel(self):
        self._cancel_armed = False
        self.b_cancel.setText("Cancelar")

    def cancel(self):
        if self.runner:
            self.b_cancel.setEnabled(False)
            self.b_cancel.setText("Cancelando…")
            self.r_title.setText("Cancelando…")
            self.runner.cancel()

    def _on_finished(self, status: str, data: dict):
        self.timer.stop()
        self._tick()
        row = self.rows[self.cur] if self.cur >= 0 else None
        if status == "ok":
            # terminou bem: a etapa em curso e as que sobraram (ex.: registro final) estão concluídas
            for i, r in enumerate(self.rows):
                if r.state in ("active", "pending"):
                    r.set_state("done")
                    self.bar.done.add(i)
            self.bar.finish("ok")
            self.r_title.setText("Concluído")
            self.r_step.setText("Assista cada clipe antes de postar. Nada foi publicado.")
        elif status == "cancelado":
            if row:
                row.set_state("cancel")
            self.bar.finish("cancel")
            self.r_title.setText("Cancelado")
            self.r_step.setText("Processamento cancelado. Nenhum arquivo foi apagado.")
            self._append(Event("info", "Processamento cancelado pelo usuário."))
        elif status == "auth_error":
            self.state.set_auth_status("auth_error", AUTH_REQUIRED_MESSAGE)
            self.preserve_form_on_return = True
            self.b_new.setText("Voltar ao formulário")
            if row:
                row.set_state("error")
            self.bar.finish("error")
            self.r_title.setText("Autenticação necessária")
            self.r_step.setText(AUTH_REQUIRED_MESSAGE)
            self._append(Event("error", AUTH_REQUIRED_MESSAGE))
            if not self.logs.expanded:
                self.logs.toggle()
        else:
            if row:
                row.set_state("error")
            self.bar.finish("error")
            self.r_title.setText("Erro no processamento")
            self.r_step.setText(data.get("error") or "Veja a resposta do agente e os logs técnicos abaixo.")
            if data.get("error"):
                self._append(Event("error", data["error"]))
            if not self.logs.expanded:
                self.logs.toggle()
        result = "" if status == "auth_error" else data.get("result", "")
        if result:
            self.answer.setMarkdown(result)
        self.b_cancel.hide()
        for b in (self.b_new, self.b_folder, self.b_lib):
            b.show()
        self.result_box.setVisible(status == "ok")
        self.result_title.setVisible(status == "ok")
        if status != "ok" and result and not self.answer_sec.expanded:
            self.answer_sec.toggle()
        job = dict(self.job or {}, status=status, elapsed=round(data.get("elapsed", 0)),
                   log=str(self.log_path) if self.log_path else "", result=result[:4000],
                   error=AUTH_REQUIRED_MESSAGE if status == "auth_error" else data.get("error", ""))
        self.finished.emit(status, job)

    def show_results(self, clips: list, show_empty: bool = True):  # noqa: D401
        """Clipes novos deste processamento (o app chama depois de reler a biblioteca)."""
        clear_layout(self.result_row)
        self.result_box.setVisible(bool(clips) or show_empty)
        self.result_title.setVisible(bool(clips) or show_empty)
        self.result_empty.setVisible(not clips)
        if not clips:
            return
        for c in clips[:5]:
            self.result_row.addWidget(self._card(c, 150))
        self.result_row.addStretch(1)

    def _new_cut(self, _checked: bool = False):
        preserve = self.preserve_form_on_return
        self.preserve_form_on_return = False
        self.b_new.setText("Novo corte")
        self.reset_form(preserve=preserve)

    def reset_form(self, preserve: bool = False):
        self.stack.setCurrentIndex(0)
        self.recent_box.show()
        if not preserve:
            self.link.edit.clear()
        self.link.edit.setFocus()
        self._render_recent()

    def _open_out(self):
        if self.job:
            open_folder(Path(self.job["out"]))

    def _copy_log(self):
        QGuiApplication.clipboard().setText(self.log.toPlainText())
        self.state.toast.emit("Log copiado.", "info")

    # ================================================================ recentes
    def _card(self, c, width: int) -> VideoCard:
        plat, date, dur = clip_meta(c)
        card = VideoCard(c, width, plat, sync_info(c), date, dur)
        card.clicked.connect(self.state.play_clip.emit)
        return card

    def _render_recent(self):
        clear_layout(self.recent_row)
        clips = self.state.clips
        if not clips:
            self.recent_row.addWidget(EmptyState("video", "Nenhum corte ainda",
                                                 "Cole um link acima e clique em Gerar clipes.", compact=True), 1)
            return
        width = 150
        view = self.scroll.viewport().width() - 2 * T.SP8 if self.scroll else self.width()
        avail = max(width, min(self.inner.maximumWidth(), view))
        n = max(1, min(8, (avail + T.SP4) // (width + T.SP4)))
        for c in clips[:n]:
            self.recent_row.addWidget(self._card(c, width))
        self.recent_row.addStretch(1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.stack.currentIndex() == 0:
            self._recent_timer.start(150)

    def on_show(self):
        self._update_start()
        if self.stack.currentIndex() == 0:
            self.link.edit.setFocus()
