import json
import sys
import tempfile
import unittest
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.codex_agent import CodexStreamParser, build_codex_command, validate_codex_artifacts
from studio import system
from studio.storage import Settings
from studio.runner import JobRunner
from PySide6.QtCore import QCoreApplication, Qt

URL = "https://www.youtube.com/watch?v=EWLoiyFsMuk"


class CodexTests(unittest.TestCase):
    def test_command_passes_prompt_via_stdin_and_explicit_output(self):
        out = Path("saída com espaços").resolve()
        argv, prompt = build_codex_command("codex", URL, "youtube", 1, out, "en")
        self.assertEqual(argv[:3], ["codex", "exec", "--json"])
        self.assertEqual(argv[-1], "-")
        self.assertIn("workspace-write", argv)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
        self.assertIn(str(out), argv)
        self.assertIn(json.dumps(str(out), ensure_ascii=False), prompt)
        self.assertIn('"legenda": "en"', prompt)
        with self.assertRaises(ValueError):
            build_codex_command("codex", URL + '; calc', "youtube", 1, out)

    def feed(self, parser, **message):
        return parser.feed(json.dumps(message))

    def test_events_and_final_result(self):
        parser = CodexStreamParser()
        events = self.feed(parser, type="item.started", item={"type": "command_execution",
                           "command": 'python -I "scripts/clipper.py" prepare URL'})
        self.assertEqual(events[0].step, "prepare")
        payload = {"status": "pulado", "summary": "Sem momentos aprovados.", "clips": [], "report": ""}
        self.feed(parser, type="item.completed", item={"type": "agent_message", "text": json.dumps(payload)})
        self.feed(parser, type="turn.completed")
        self.assertFalse(parser.result["is_error"])
        self.assertEqual(parser.result["payload"], payload)

    def test_failure_is_not_overwritten_by_completion(self):
        parser = CodexStreamParser()
        self.feed(parser, type="turn.failed", error={"message": "Quota excedida"})
        self.feed(parser, type="turn.completed")
        self.assertTrue(parser.result["is_error"])
        self.assertIn("Quota", parser.result["result"])

    def test_plain_text_and_missing_result_are_not_success(self):
        parser = CodexStreamParser()
        self.assertIsNone(parser.result)
        self.feed(parser, type="item.completed", item={"type": "agent_message", "text": "Pronto!"})
        self.feed(parser, type="turn.completed")
        self.assertTrue(parser.result["is_error"])
        self.assertEqual(parser.feed("[1,2]"), [])

    def test_artifact_validation_requires_files_and_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / "clip.mp4"
            report = root / "report.md"
            result = {"payload": {"status": "ok", "clips": [str(clip)], "report": str(report)}}
            self.assertTrue(validate_codex_artifacts(result, root))
            clip.write_bytes(b"test")
            report.write_text(f"{clip}\nsync FAIL\n", encoding="utf-8")
            self.assertTrue(validate_codex_artifacts(result, root))
            report.write_text(f"{clip}\nsync ok: speech ok, captions ok\n", encoding="utf-8")
            self.assertEqual(validate_codex_artifacts(result, root), "")
            self.assertTrue(validate_codex_artifacts(result, root / "other"))
            result["payload"]["clips"] = []
            self.assertTrue(validate_codex_artifacts(result, root))

    @patch("studio.system.run", return_value=(0, "Logged in using ChatGPT"))
    @patch("studio.system.find_codex", return_value="codex.exe")
    def test_codex_auth_command(self, _find, run):
        self.assertEqual(system.check_agent_auth("codex")[0], "connected")
        run.assert_called_once_with(["codex.exe", "login", "status"], timeout=20)

    def test_settings_preserve_claude_and_codex_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"claude_path": "old.exe"}', encoding="utf-8")
            settings = Settings(path)
            self.assertEqual(settings["agent"], "claude")
            settings["agent"] = "codex"
            settings["codex_path"] = "codex.exe"
            settings.save()
            restored = Settings(path)
            self.assertEqual(restored.agent_path, "codex.exe")
            self.assertEqual(restored["claude_path"], "old.exe")

    def test_runner_delivers_utf8_stdin_and_finishes_without_artifacts_on_skip(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = (
                "import json,sys,os; "
                "prompt=sys.stdin.buffer.read().decode('utf-8'); "
                "assert prompt == 'ação e tradução'; "
                "assert 'CODEX_WINDOWS_REGISTERED_CORE' not in os.environ; "
                "p={'status':'pulado','summary':'Sem momentos aprovados.','clips':[],'report':''}; "
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(p)}})); "
                "print(json.dumps({'type':'turn.completed'}))"
            )
            runner = JobRunner([sys.executable, "-c", code], root / "log.txt",
                               prompt="ação e tradução", agent="codex", out_dir=root)
            done = threading.Event()
            results = []
            def finish(status, data):
                results.append((status, data))
                done.set()
            runner.finished.connect(finish, Qt.DirectConnection)
            with patch.dict("os.environ", {"CODEX_WINDOWS_REGISTERED_CORE": "1"}):
                runner.start()
            if not done.wait(15):
                runner.cancel()
                self.fail("O runner não terminou após o EOF de stdin.")
            self.assertEqual(results[0][0], "ok", results)
            self.assertIn("Sem momentos", results[0][1]["result"])
            runner.proc.stdout.close()
            runner.proc.stderr.close()

    def test_cancel_preserves_existing_job_files(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "transcript.json"
            existing.write_text("{}", encoding="utf-8")
            runner = JobRunner([sys.executable, "-c", "import time; time.sleep(30)"],
                               root / "log.txt", agent="codex", out_dir=root)
            done = threading.Event()
            results = []
            def finish(status, _data):
                results.append(status)
                done.set()
            runner.finished.connect(finish, Qt.DirectConnection)
            runner.start()
            runner.cancel()
            self.assertTrue(done.wait(15))
            self.assertEqual(results, ["cancelado"])
            self.assertEqual(existing.read_text(encoding="utf-8"), "{}")
            runner.proc.stdout.close()
            runner.proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
