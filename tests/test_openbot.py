import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("setup_openbot", ROOT / "scripts/setup-openbot.py")
setup_openbot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_openbot)


@unittest.skipUnless(os.name == "posix", "Linux shell launchers")
class OpenBotSetupTests(unittest.TestCase):
    def fixture(self, root):
        home = root / "home with space"
        (home / ".agents/skills").mkdir(parents=True)
        template = root / "openbot.desktop"
        template.write_text("[Desktop Entry]\nName=OpenBot\nExec=openbot %U\nIcon=openbot\nType=Application\n")
        application = root / "application"
        application.write_text(
            "#!/usr/bin/env python3\nimport json, os, sys\n"
            "print(json.dumps({'provider': os.getenv('OPENBOT_CODEX_PATH'), 'args': sys.argv[1:]}))\n"
        )
        application.chmod(0o755)
        xingchi = root / "xingchi"
        xingchi.write_text("#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
        xingchi.chmod(0o755)
        return home, application, xingchi, template

    def test_installs_working_launchers_without_mutating_shared_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            home, app, xingchi, template = self.fixture(Path(directory))
            paths = setup_openbot.setup(home, app, xingchi, template, False)
            self.assertEqual(len(paths), 3)
            self.assertFalse((home / ".local").exists())
            self.assertEqual(paths, setup_openbot.setup(home, app, xingchi, template, True))
            launch = subprocess.run([str(home / ".local/bin/openbot"), "openbot://test"], capture_output=True, text=True, check=True)
            output = json.loads(launch.stdout)
            self.assertEqual(output["args"], ["openbot://test"])
            provider = Path(output["provider"])
            result = subprocess.run([str(provider), "app-server", "--listen", "stdio://"], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), [
                "-c", 'model="gpt-6.1-sol"', "-c", 'sandbox_mode="danger-full-access"',
                "-c", 'approval_policy="never"', "app-server", "--listen", "stdio://",
            ])
            self.assertEqual(setup_openbot.setup(home, app, xingchi, template, True), [])
            self.assertEqual(list((home / ".agents/skills").iterdir()), [])
            self.assertFalse((home / ".codex").exists())

    def test_preserves_custom_desktop_fields_and_original_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            home, app, xingchi, template = self.fixture(Path(directory))
            desktop = home / ".local/share/applications/openbot.desktop"
            desktop.parent.mkdir(parents=True)
            original = template.read_text() + "Comment=My settings\n[Desktop Action Logs]\nExec=openbot-logs\n"
            desktop.write_text(original)
            setup_openbot.setup(home, app, xingchi, template, True)
            self.assertIn("Comment=My settings", desktop.read_text())
            self.assertIn("[Desktop Action Logs]\nExec=openbot-logs", desktop.read_text())
            self.assertEqual(desktop.with_name("openbot.desktop.xingchi.bak").read_text(), original)

    def test_refuses_unmanaged_wrapper_before_writing_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            home, app, xingchi, template = self.fixture(Path(directory))
            launcher = home / ".local/bin/openbot"
            launcher.parent.mkdir(parents=True)
            launcher.write_text("my existing command")
            with self.assertRaisesRegex(ValueError, "unmanaged launcher"):
                setup_openbot.setup(home, app, xingchi, template, True)
            self.assertEqual(launcher.read_text(), "my existing command")
            self.assertFalse((launcher.parent / "xingchi-openbot-codex").exists())

    def test_desktop_command_escapes_reserved_characters(self):
        self.assertEqual(setup_openbot.desktop_command(Path('/home/a%/$b"/openbot')),
                         '"/home/a%%/\\\\$b\\\\"/openbot" %U')
