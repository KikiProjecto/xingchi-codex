import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "POSIX launchers are tested on macOS/Linux")
class LauncherTests(unittest.TestCase):
    def test_continue_forks_history_without_switching_the_selected_key(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            xdir = home / ".xingchi"
            xdir.mkdir()
            (xdir / "upstream.key").write_text("public-test-key\n")
            (xdir / "astra.key").write_text("dedicated-test-key\n")
            fake = home / "codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json, os, sys\n"
                "print(json.dumps({'args': sys.argv[1:], "
                "'key': os.getenv('XINGCHI_API_KEY')}))\n"
            )
            fake.chmod(0o755)
            for flags, key in (([], "public-test-key"), (["--astra"], "dedicated-test-key")):
                with self.subTest(flags=flags):
                    result = subprocess.run(
                        ["sh", str(ROOT / "bin/xingchi-codex"), *flags,
                         "--continue", "-c", "model_reasoning_effort=high", "--search"],
                        env={"HOME": str(home), "CODEX_HOME": str(home / ".codex"),
                             "PATH": str(home) + os.pathsep + os.environ["PATH"]},
                        capture_output=True, text=True, check=True,
                    )
                    output = json.loads(result.stdout)
                    self.assertEqual(output["args"], ["--no-daemon", "fork", "--last",
                                                     "-c", "model_reasoning_effort=high", "--search"])
                    self.assertEqual(output["key"], key)

    def test_codex_launcher_forwards_args_and_reads_key(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            xdir = home / ".xingchi"
            xdir.mkdir()
            (xdir / "upstream.key").write_text("local-test-key\n")
            (xdir / "astra.key").write_text("astra-test-key\n")

            fake = home / "codex"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "print(json.dumps({'args': sys.argv[1:], "
                "'url': os.getenv('OPENAI_BASE_URL'), "
                "'key': os.getenv('OPENAI_API_KEY'), "
                "'selected': os.getenv('XINGCHI_API_KEY'), "
                "'astra_env': os.getenv('XINGCHI_ASTRA_API_KEY')}))\n"
            )
            fake.chmod(0o755)

            result = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--model", "two words",
                 "-a", "on-request", "-s", "read-only", "--approve-for-me",
                 "--search", "-c", "model_reasoning_effort=high", "*"],
                env={
                    "PATH": str(home) + os.pathsep + os.environ["PATH"],
                    "HOME": str(home),
                    "XINGCHI_HOME": str(xdir),
                    "XINGCHI_ASTRA_API_KEY": "must-not-leak-to-codex",
                },
                capture_output=True,
                text=True,
                check=True,
            )
            output = json.loads(result.stdout)
            # A shared daemon can retain the catalog from before installation.
            self.assertEqual(output["args"], [
                "--no-daemon", "--model", "two words", "-a", "on-request",
                "-s", "read-only", "--approve-for-me", "--search", "-c",
                "model_reasoning_effort=high", "*",
            ])
            self.assertEqual(output["url"], "https://api.xingchiapi.com/v1")
            self.assertEqual(output["key"], "local-test-key")
            self.assertEqual(output["selected"], "local-test-key")
            self.assertIsNone(output["astra_env"])

    def test_astra_flag_selects_only_astra_key_and_defaults_to_astra_model(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            xdir = home / ".xingchi"
            xdir.mkdir()
            (xdir / "upstream.key").write_text("sol-test-key\n")
            (xdir / "astra.key").write_text("astra-test-key\n")
            fake = home / "codex"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "print(json.dumps({'args': sys.argv[1:], 'key': os.getenv('XINGCHI_API_KEY'), "
                "'astra_env': os.getenv('XINGCHI_ASTRA_API_KEY')}))\n"
            )
            fake.chmod(0o755)

            result = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--astra", "--help"],
                env={"PATH": str(home) + os.pathsep + os.environ["PATH"],
                     "HOME": str(home), "XINGCHI_HOME": str(xdir)},
                capture_output=True, text=True, check=True,
            )
            output = json.loads(result.stdout)
            self.assertEqual(output["args"], ["--no-daemon", "-m", "gpt-6-astra", "--help"])
            self.assertEqual(output["key"], "astra-test-key")
            self.assertIsNone(output["astra_env"])

    def test_group_launcher_preserves_a_saved_model_in_that_group(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            xdir = home / ".xingchi"
            codex_home = home / ".codex"
            xdir.mkdir()
            codex_home.mkdir()
            (xdir / "upstream.key").write_text("sol-test-key\n")
            (xdir / "astra.key").write_text("astra-test-key\n")
            (codex_home / "config.toml").write_text('model = "gpt-6.1-sol"\n')
            (codex_home / "xingchi-models.json").write_text(
                '{"models":[{"slug":"gpt-6.1-sol"}]}\n'
            )
            astra_catalog = codex_home / "xingchi-models-astra.json"
            astra_catalog.write_text('{"models":[{"slug":"gpt-6-astra"}]}\n')
            fake = home / "codex"
            fake.write_text("#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
            fake.chmod(0o755)
            env = {"PATH": str(home) + os.pathsep + os.environ["PATH"],
                   "HOME": str(home), "CODEX_HOME": str(codex_home), "XINGCHI_HOME": str(xdir)}
            sol = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--help"],
                env=env, capture_output=True, text=True, check=True,
            )
            astra = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--astra", "--help"],
                env=env, capture_output=True, text=True, check=True,
            )
            sol_args = json.loads(sol.stdout)
            astra_args = json.loads(astra.stdout)
            self.assertNotIn("-m", sol_args, "keep the saved Sol model selection")
            self.assertIn("-m", astra_args)
            self.assertIn("gpt-6-astra", astra_args)
            self.assertIn(str(astra_catalog), " ".join(astra_args))

            (codex_home / "config.toml").write_text('model = "gpt-6-astra"\n')
            selected_astra = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--astra", "--help"],
                env=env, capture_output=True, text=True, check=True,
            )
            selected_sol = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--help"],
                env=env, capture_output=True, text=True, check=True,
            )
            self.assertNotIn("-m", json.loads(selected_astra.stdout))
            self.assertIn("-m", json.loads(selected_sol.stdout))

    def test_astra_flag_respects_an_explicit_model_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            xdir = home / ".xingchi"
            xdir.mkdir()
            (xdir / "astra.key").write_text("astra-test-key\n")
            fake = home / "codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json, os, sys\n"
                "print(json.dumps({'args': sys.argv[1:], 'key': os.getenv('XINGCHI_API_KEY')}))\n"
            )
            fake.chmod(0o755)
            result = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--astra", "exec", "-m",
                 "gpt-6-luna", "say hi"],
                env={"PATH": str(home) + os.pathsep + os.environ["PATH"],
                     "HOME": str(home), "XINGCHI_HOME": str(xdir)},
                capture_output=True, text=True, check=True,
            )
            output = json.loads(result.stdout)
            self.assertEqual(output["args"], [
                "--no-daemon", "exec", "-m", "gpt-6-luna", "say hi",
            ])
            self.assertEqual(output["key"], "astra-test-key")

    def test_astra_flag_fails_closed_when_astra_key_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            xdir = home / ".xingchi"
            xdir.mkdir()
            (xdir / "upstream.key").write_text("sol-test-key\n")
            result = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--astra", "--help"],
                env={"PATH": os.environ["PATH"], "HOME": str(home), "XINGCHI_HOME": str(xdir)},
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Astra API key missing", result.stderr)
            self.assertNotIn("sol-test-key", result.stderr)

    def test_codex_launcher_errors_without_key(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            result = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi-codex"), "--help"],
                env={"PATH": os.environ["PATH"], "HOME": str(home)},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("API key missing", result.stderr)

    def test_doctor_reports_model_and_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            fake = home / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "echo '  model                    gpt-6.1-sol · OpenAI'\n"
                "echo '  default model provider   OpenAI'\n"
                "echo '  OpenAI API inference URL https://api.xingchiapi.com/v1/x reachable (HTTP 404)'\n"
                "echo '  unrelated noise line'\n"
                "exit 0\n"
            )
            fake.chmod(0o755)
            result = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi"), "--doctor"],
                env={"PATH": str(home) + os.pathsep + os.environ["PATH"], "HOME": str(home)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("gpt-6.1-sol", result.stdout)
            self.assertIn("OpenAI", result.stdout)
            self.assertNotIn("unrelated noise", result.stdout)
            self.assertIn("codex doctor: healthy", result.stdout)

    def test_doctor_propagates_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            fake = home / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "echo '  model                    gpt-6.1-sol · OpenAI'\n"
                "echo 'failed check'\n"
                "exit 3\n"
            )
            fake.chmod(0o755)
            result = subprocess.run(
                ["sh", str(ROOT / "bin/xingchi"), "--doctor"],
                env={"PATH": str(home) + os.pathsep + os.environ["PATH"], "HOME": str(home)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 3)
            self.assertIn("reported problems (exit 3)", result.stdout)

    def test_unknown_option_rejected(self):
        result = subprocess.run(
            ["sh", str(ROOT / "bin/xingchi"), "--bogus"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown option", result.stderr)

    def test_repo_is_codex_only(self):
        self.assertEqual(sorted(p.name for p in (ROOT / "bin").iterdir()
                                if p.name != "__pycache__"),
                         ["xingchi", "xingchi-codex", "xingchi-codex-runner.py", "xingchi_conpty.py",
                          "xingchi_history.py", "xingchi_tui.py"])
        self.assertFalse((ROOT / "share").exists())

    def test_installers_match_direct_upstream(self):
        unix = (ROOT / "install.sh").read_text()
        windows = (ROOT / "install.ps1").read_text()
        for text in (unix, windows):
            self.assertIn("gpt-6.1-sol", text)
            self.assertIn("https://api.xingchiapi.com/v1", text)
            self.assertIn("xingchi-codex", text)
            self.assertIn("integrations.py", text)
            self.assertIn('/inherit automatically uses Full access and approval policy never', text)
            self.assertIn('Other chats keep their existing permissions.', text)
            self.assertIn("XINGCHI_SKIP_INTEGRATIONS", text)
            for leftover in ("litellm", "4010", "bridge.key", "bridge-up"):
                self.assertNotIn(leftover, text.lower())

    def test_installers_and_readme_explain_both_keys_and_unified_skills(self):
        unix = (ROOT / "install.sh").read_text(encoding="utf-8")
        windows = (ROOT / "install.ps1").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for text, skill_path in ((unix, ".agents/skills"), (windows, "agents\\skills")):
            for required in (
                "upstream.key", "astra.key", "XINGCHI_API_KEY",
                "XINGCHI_ASTRA_API_KEY", "xingchi-codex --astra",
                "xingchi-codex --continue",
                "Type / to select /inherit",
                "exit any running Codex and relaunch xingchi-codex",
                "gpt-6-astra", "xingchi-models.json",
                "xingchi-models-astra.json", "XINGCHI_SKIP_INTEGRATIONS",
                skill_path,
                "skill-conflicts.json",
            ):
                self.assertIn(required, text)
            self.assertIn("GPT公益", text)
            self.assertIn("Astra-专属余额", text)

        for required in (
            "GPT公益/Sol", "Astra-专属余额", "xingchi-codex --astra",
            "xingchi-codex --continue",
            "xingchi-codex -m gpt-6.1-sol", "xingchi-codex --astra -m gpt-6-astra",
            "xingchi-models-astra.json",
        ):
            self.assertIn(required, readme)

    def test_readme_matches_direct_upstream(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("gpt-6.1-sol", readme)
        self.assertIn("api.xingchiapi.com", readme)
        self.assertIn("Responses", readme)
        self.assertNotIn("master_key", readme)
        self.assertNotIn("litellm.yaml", readme.lower())

    def test_installer_trims_padded_key_and_writes_everything(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            fakepath = home / "fakebin"
            fakepath.mkdir()
            (fakepath / "codex").write_text("#!/bin/sh\necho 'codex-cli 0.170.0'\n")
            (fakepath / "codex").chmod(0o755)
            payloads = ("xingchi-codex-runner.py", "xingchi_history.py", "xingchi_tui.py", "xingchi_conpty.py")
            target = home / "bin"
            target.mkdir()
            for name in payloads:
                (target / name).write_text("# stale installation\n")

            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--yes"],
                env={
                    "HOME": str(home),
                    "PATH": str(fakepath) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
                    "XINGCHI_HOME": str(home / ".xingchi"),
                    "XINGCHI_BIN": str(home / "bin"),
                    "XINGCHI_UPSTREAM": "http://127.0.0.1:9/v1",
                    "XINGCHI_API_KEY": "  padded-key  \r",
                    "SHELL": "/bin/sh",
                },
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Installation complete", result.stdout)
            self.assertIn("GPT公益", result.stdout)
            self.assertIn("Astra-专属余额", result.stdout)
            self.assertIn("xingchi-codex --astra", result.stdout)
            self.assertIn(".agents/skills", result.stdout)
            # The pasted key is trimmed before it reaches any file.
            self.assertEqual((home / ".xingchi/upstream.key").read_text(), "padded-key\n")
            config_text = (home / ".codex/config.toml").read_text()
            self.assertIn('env_key = "XINGCHI_API_KEY"', config_text)
            self.assertNotIn('env_key = "XINGCHI_ASTRA_API_KEY"', config_text)
            self.assertNotIn("padded-key", config_text)
            self.assertNotIn("padded-key  ", config_text)
            launcher = home / "bin/xingchi-codex"
            self.assertTrue(launcher.exists())
            self.assertEqual(launcher.stat().st_mode & 0o777, 0o755)
            settings = tomllib.loads(config_text)
            self.assertEqual(settings["model_providers"]["OpenAI"]["capabilities"]["remote_compaction"], "unsupported")
            catalog = json.loads(Path(settings["model_catalog_json"]).read_text())
            self.assertEqual([model["slug"] for model in catalog["models"]], ["gpt-6.1-sol"])
            astra_catalog = json.loads((home / ".codex/xingchi-models-astra.json").read_text())
            self.assertEqual([model["slug"] for model in astra_catalog["models"]],
                             json.loads((ROOT / "lib/model-groups.json").read_text())["astra"])
            self.assertEqual(settings["features"], {
                "api_key_model_discovery": True, "image_generation": True, "goals": True,
            })
            self.assertIn("xingchi-codex-runner.py", launcher.read_text())
            for name in payloads:
                self.assertEqual((target / name).read_bytes(), (ROOT / "bin" / name).read_bytes(),
                                 f"The installer left an outdated {name}")
                self.assertEqual((home / ".xingchi/bin" / name).read_bytes(), (target / name).read_bytes(),
                                 f"The Xingchi runtime copy left an outdated {name}")
            self.assertEqual((home / ".xingchi/bin/xingchi-codex").stat().st_mode & 0o777, 0o755)

    def test_installer_upgrades_old_cli_and_preserves_custom_home_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            fakepath = home / "fakebin"
            fakepath.mkdir()
            codex = fakepath / "codex"
            codex.write_text("#!/bin/sh\necho 'codex-cli 0.169.0'\n")
            codex.chmod(0o755)
            npm = fakepath / "npm"
            npm.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" > "$XINGCHI_TEST_NPM_LOG"\n'
                'printf "#!/bin/sh\\necho codex-cli 0.170.0\\n" > "$XINGCHI_TEST_CODEX"\n'
            )
            npm.chmod(0o755)
            codex_home = home / "Custom Codex Home"
            codex_home.mkdir()
            config = codex_home / "config.toml"
            xingchi_home = home / ".xingchi"
            xingchi_home.mkdir()
            (xingchi_home / "models.txt").write_text("sol:gpt-6.1-terra\n")
            config.write_text('model = "gpt-6.1-terra"\nmodel_reasoning_effort = "max"\n')
            npm_log = home / "npm.log"
            result = subprocess.run(
                ["sh", str(ROOT / "install.sh"), "--yes"],
                env={"HOME": str(home), "PATH": str(fakepath) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
                     "CODEX_HOME": str(codex_home), "XINGCHI_HOME": str(xingchi_home),
                     "XINGCHI_BIN": str(xingchi_home / "bin") + "/", "XINGCHI_API_KEY": "test-key",
                     "XINGCHI_UPSTREAM": "http://127.0.0.1:9/v1", "SHELL": "/bin/sh",
                     "XINGCHI_TEST_NPM_LOG": str(npm_log), "XINGCHI_TEST_CODEX": str(codex)},
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(npm_log.read_text().strip(), "install -g @openai/codex")
            self.assertEqual((xingchi_home / "bin/xingchi_history.py").read_bytes(),
                             (ROOT / "bin/xingchi_history.py").read_bytes())
            settings = tomllib.loads(config.read_text())
            self.assertEqual(settings["model"], "gpt-6.1-terra")
            self.assertEqual(settings["model_reasoning_effort"], "max")
            self.assertEqual(Path(settings["model_catalog_json"]).parent, codex_home)
            self.assertEqual(settings["model_providers"]["OpenAI"]["capabilities"]["remote_compaction"], "unsupported")

    def test_installer_restores_echo_if_key_prompt_is_interrupted(self):
        unix = (ROOT / "install.sh").read_text()
        self.assertIn("trap 'stty echo", unix)
        self.assertIn("stty echo", unix)

    def test_no_credentials_in_repo(self):
        patterns = [
            re.compile(r"sk-[0-9a-fA-F]{32,}"),
            re.compile(r"(?:ghp|github_pat|xox[baprs])_[A-Za-z0-9_-]{20,}"),
            re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
            re.compile(r"postgres(?:ql)?://[^/\\s:]+:[^@\\s]+@"),
        ]
        for path in ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts:
                continue
            if path.name.endswith((".pyc", ".png", ".jpg", ".zip")):
                continue
            text = path.read_text(errors="ignore")
            for pattern in patterns:
                self.assertIsNone(pattern.search(text), f"secret-like value in {path}")

    def test_no_local_workspace_metadata_is_shipped(self):
        # Ignored local metadata may exist in a developer checkout; verify it
        # is not tracked/distributed instead of requiring a clean home folder.
        for name in (".claude", ".freebuff"):
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", name], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.assertNotEqual(result.returncode, 0, f"{name} is tracked in the repository")


if __name__ == "__main__":
    unittest.main()
