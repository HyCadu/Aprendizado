"""Roda o Claude Code (que roda os scripts das skills) num processo separado e emite eventos para a UI."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .core import REPO, Event, StreamParser, clear_stale_whisper_lock, redact

NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class JobRunner(QObject):
    event = Signal(object)          # Event
    finished = Signal(str, object)  # status: ok | erro | cancelado ; dados finais (dict)

    def __init__(self, argv: list[str], log_path: Path, python_dir: str | None = None, prompt: str = "",
                 parent=None):
        super().__init__(parent)
        self.argv = argv
        self.python_dir = python_dir
        self.prompt = prompt
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None
        self.parser = StreamParser()
        self.cancelled = False
        self.started_at = 0.0
        self._log = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------ ciclo de vida
    def start(self):
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        if self.python_dir:
            # As skills chamam `python` e as permissões só liberam `python ...`. Sem isto, no Windows o
            # `python` pode cair no atalho da Microsoft Store ("Python was not found").
            py = Path(self.python_dir)
            env["PATH"] = os.pathsep.join([str(py), str(py / "Scripts"), env.get("PATH", "")])
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log = open(self.log_path, "w", encoding="utf-8")
        self._write_log(f"# {time.strftime('%Y-%m-%d %H:%M:%S')}  {redact(self.prompt)}\n")
        self.started_at = time.time()
        self._clear_lock()
        try:
            self.proc = subprocess.Popen(
                self.argv, cwd=str(REPO), env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
        except OSError as e:
            self._emit(Event("error", f"Não consegui iniciar o Claude Code: {e}"))
            self._close("erro", {"error": str(e)})
            return
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def cancel(self):
        """Encerra o Claude e todos os processos filhos (python, ffmpeg). Não apaga nenhum arquivo:
        o que já foi baixado/transcrito fica na pasta do job."""
        if not self.running():
            return
        self.cancelled = True
        self._emit(Event("info", "Cancelando: encerrando o Claude Code e os scripts…"))
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                               capture_output=True, creationflags=NO_WINDOW, timeout=20)
            else:
                self.proc.terminate()
        except (OSError, subprocess.TimeoutExpired):
            try:
                self.proc.kill()
            except OSError:
                pass

    # ------------------------------------------------------------ leitura
    def _emit(self, ev: Event):
        self._write_log(f"[{ev.kind}] {ev.text}\n")
        self.event.emit(ev)

    def _write_log(self, s: str):
        with self._lock:
            if self._log:
                try:
                    self._log.write(s)
                    self._log.flush()
                except (OSError, ValueError):
                    pass

    def _read_stdout(self):
        for raw in iter(self.proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace")
            for ev in self.parser.feed(line):
                self._emit(ev)
        code = self.proc.wait()
        if self.cancelled:
            self._clear_lock()  # o python foi morto à força e não soltou a trava da GPU
        res = self.parser.result or {}
        data = {"returncode": code, "result": redact(str(res.get("result") or "")),
                "duration_ms": res.get("duration_ms"), "elapsed": time.time() - self.started_at}
        if self.cancelled:
            status = "cancelado"
        elif code == 0 and res and not res.get("is_error"):
            status = "ok"
        else:
            status = "erro"
            if not res:
                data["error"] = f"O Claude Code terminou sem resultado (código {code})."
        self._close(status, data)

    def _clear_lock(self):
        pid = clear_stale_whisper_lock()
        if pid is not None:
            self._emit(Event("info", f"Trava da GPU deixada por uma transcrição interrompida (PID {pid}) removida."))

    def _read_stderr(self):
        for raw in iter(self.proc.stderr.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                self._emit(Event("raw", redact(line)))

    def _close(self, status: str, data: dict):
        self._write_log(f"\n# fim: {status}\n")
        with self._lock:
            if self._log:
                self._log.close()
                self._log = None
        self.finished.emit(status, data)
