import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio import core, system
from studio.core import Event
from studio.runner import JobRunner


class ClaudeAuthStatusTests(unittest.TestCase):
    def test_status_json_distinguishes_connected_and_disconnected(self):
        self.assertEqual(system.parse_claude_auth_status(0, '{"loggedIn": true}')[0], "connected")
        self.assertEqual(system.parse_claude_auth_status(1, '{"loggedIn": false}')[0], "disconnected")

    def test_status_text_distinguishes_logged_out_from_auth_error(self):
        status, _ = system.parse_claude_auth_status(1, "Not logged in. Please run /login")
        self.assertEqual(status, "disconnected")
        status, _ = system.parse_claude_auth_status(1, "OAuth token expired")
        self.assertEqual(status, "auth_error")

    @patch("studio.system.run", return_value=(0, "Logged in as user@example.com"))
    @patch("studio.system.find_claude", return_value="claude")
    def test_check_uses_official_auth_status_command(self, _find, run):
        status, _ = system.check_claude_auth()
        self.assertEqual(status, "connected")
        run.assert_called_once_with(["claude", "auth", "status"], timeout=20)

    @patch("studio.system.find_claude", return_value=None)
    def test_missing_cli_is_unavailable(self, _find):
        status, _ = system.check_claude_auth()
        self.assertEqual(status, "unavailable")

    @unittest.skipUnless(os.name == "nt", "A abertura do terminal usa o console do Windows.")
    @patch("studio.system.subprocess.Popen")
    @patch("studio.system.find_claude", return_value=r"C:\Program Files\Claude\claude.cmd")
    def test_login_opens_interactive_console_with_official_command(self, _find, popen):
        ok, _ = system.launch_claude_login()
        self.assertTrue(ok)
        command = popen.call_args.args[0]
        self.assertEqual(command[:2], [os.environ.get("COMSPEC", "cmd.exe"), "/k"])
        self.assertIn("auth login", command[2])
        self.assertEqual(popen.call_args.kwargs["creationflags"], subprocess.CREATE_NEW_CONSOLE)


class AuthenticationErrorTests(unittest.TestCase):
    def test_authentication_error_markers(self):
        self.assertTrue(core.is_authentication_error("Not logged in. Please run /login"))
        self.assertTrue(core.is_authentication_error("OAuth token expired"))
        self.assertFalse(core.is_authentication_error("Transcription completed successfully"))

    def test_runner_reports_localized_auth_error(self):
        runner = JobRunner(["claude"], Path("test.log"))
        events = []
        runner.event.connect(events.append)

        runner._emit(Event("raw", "Not logged in. Please run /login"))

        self.assertTrue(runner.authentication_error)
        self.assertEqual(events[0].kind, "error")
        self.assertTrue(events[0].data["auth_error"])
        self.assertIn("Configurações", events[0].text)


if __name__ == "__main__":
    unittest.main()
