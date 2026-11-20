"""Executa um corte com o mesmo adaptador Codex da interface, sem abrir a janela."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Slot

from studio.codex_agent import build_codex_command, find_codex
from studio.core import DEFAULT_YT_OUT, detect_platform, redact
from studio.runner import JobRunner
from studio.system import check_agent_auth, find_python


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--top", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--legenda", choices=("pt", "en"), default="pt")
    parser.add_argument("--out", type=Path, default=DEFAULT_YT_OUT)
    args = parser.parse_args()
    platform = detect_platform(args.url)
    if platform is None:
        parser.error("Link inválido. Use um vídeo do YouTube ou VOD da Twitch.")
    executable = find_codex()
    status, detail = check_agent_auth("codex")
    if status != "connected":
        parser.exit(1, detail + "\n")
    args.out = args.out.expanduser().resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    argv, prompt = build_codex_command(executable, args.url, platform, args.top, args.out, args.legenda)
    log = args.out / "logs" / ("codex_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
    app = QCoreApplication(sys.argv)
    python = find_python()
    runner = JobRunner(argv, log, str(Path(python).parent) if python else None, prompt,
                       agent="codex", out_dir=args.out)

    class Console(QObject):
        @Slot(object)
        def on_event(self, event):
            # O log completo fica em disco; saída compacta para acompanhar o processamento.
            print(f"[{event.kind}] {event.text[:1800]}", flush=True)

        @Slot(str, object)
        def finished(self, status, data):
            print(redact(json.dumps({"status": status, **data, "log": str(log)}, ensure_ascii=False)), flush=True)
            app.exit(0 if status == "ok" else 1)

    console = Console()
    runner.event.connect(console.on_event)
    runner.finished.connect(console.finished)
    QTimer.singleShot(0, runner.start)
    try:
        return app.exec()
    finally:
        if runner.running():
            runner.cancel()


if __name__ == "__main__":
    sys.exit(main())
