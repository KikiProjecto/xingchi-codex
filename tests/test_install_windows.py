"""Windows regression test for install.ps1.

The original Windows installer used ``$Upstream`` for the base URL and
``$upstream`` for the API key. PowerShell variable names are case-insensitive,
so the two were the same variable: storing the key overwrote the URL. The
result was ``base_url = "<api key>"`` in config.toml, ``OPENAI_BASE_URL`` set to
the key in the generated launcher, and a "verification" step that tried to
DNS-resolve the key as a hostname (printed as "could not reach upstream
/models").

These tests pin that down from both ends: statically, that the colliding name
cannot come back, and functionally, that a real installer run puts the key in
the bearer token and nowhere near a URL.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import tomllib
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parents[1]
KEY = "win-test-key-abc123"
ASTRA_KEY = "win-test-astra-key-xyz789"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")

try:
    import winreg
except ImportError:  # not on Windows
    winreg = None


def _user_path():
    """The user PATH the installer would rewrite, straight from the registry."""
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, "Path")[0]
    except FileNotFoundError:
        return None


def _installer_code():
    """install.ps1 with its comment lines dropped.

    The header comment deliberately names the old $Upstream/$upstream pair, so
    the guard has to look at code only.
    """
    kept = [
        line
        for line in (ROOT / "install.ps1").read_text(encoding="utf-8-sig").splitlines()
        if not line.lstrip().startswith("#")
    ]
    return os.linesep.join(kept)


class _ModelsHandler(BaseHTTPRequestHandler):
    """Answers GET /models like the upstream and records what was sent."""

    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError):
            # PowerShell may reset a keep-alive connection it has finished with.
            pass

    def do_GET(self):
        self.server.requests.append(
            {"path": self.path, "authorization": self.headers.get("Authorization")}
        )
        if self.headers.get("Authorization") == "Bearer " + KEY:
            models = ["gpt-6.1-sol"]
        else:
            models = json.loads((ROOT / "lib/model-groups.json").read_text(encoding="utf-8"))["astra"]
        body = json.dumps({"object": "list", "data": [{"id": model} for model in models]}).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, BrokenPipeError):
            # PowerShell can reset a reused connection after reading the body.
            pass

    def log_message(self, *args):
        pass


class InstallerSourceTests(unittest.TestCase):
    """Static guards: these run on every platform, no PowerShell needed."""

    def test_powershell_installer_has_utf8_bom_for_windows_powershell_51(self):
        self.assertTrue((ROOT / "install.ps1").read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_no_case_colliding_url_and_key_variables(self):
        # To PowerShell, $Upstream and $upstream are one variable. Any spelling
        # of that name is the landmine that broke the installer.
        self.assertIsNone(
            re.search(r"\$upstream\b", _installer_code(), re.IGNORECASE),
            "install.ps1 reintroduced $Upstream/$upstream. PowerShell variable "
            "names are case-insensitive, so the base URL and the API key collide "
            "and the key ends up in base_url",
        )

    def test_launchers_are_generated_from_placeholders(self):
        # Values are filled in with a literal .Replace() into single-quoted
        # here-strings, so nothing can expand into the wrong slot.
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn("__BASE_URL__", text)
        self.assertIn("__KEY_FILE__", text)

    def test_both_saved_keys_get_user_restricted_windows_acls(self):
        text = (ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn("function Protect-UserFile($Path)", text)
        self.assertIn("$acl.SetAccessRuleProtection($true, $false)", text)
        self.assertIn("Protect-UserFile $KeyFile", text)
        self.assertIn("Protect-UserFile $AstraKeyFile", text)

    def test_launcher_loads_catalog_without_shared_daemon(self):
        self.assertIn("xingchi-codex-runner.py", _installer_code())
        self.assertIn("%XINGCHI_RUNNER%", _installer_code())

    def test_installer_refreshes_every_inherit_helper(self):
        code = _installer_code()
        for name in ("xingchi_history.py", "xingchi_tui.py", "xingchi_conpty.py"):
            self.assertIn(f"Copy-Item (Join-Path $SelfDir 'bin\\{name}') "
                          f"(Join-Path $Bin '{name}') -Force", code)
        self.assertIn("$RuntimeBin = Join-Path $XDir 'bin'", code)
        self.assertIn('Copy-Item (Join-Path $Bin $runtime) (Join-Path $RuntimeBin $runtime) -Force', code)
        for name in ('xingchi-codex.cmd', 'xingchi.cmd', 'xingchi-codex-runner.py',
                     'xingchi_history.py', 'xingchi_tui.py', 'xingchi_conpty.py'):
            self.assertIn("'" + name + "'", code)


@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class PowerShellModuleTests(unittest.TestCase):
    def test_installer_prefers_running_hosts_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            module_root = home / "foreign-modules"
            module = module_root / "Microsoft.PowerShell.Security"
            module.mkdir(parents=True)
            (module / "Microsoft.PowerShell.Security.psd1").write_text(
                "@{ ModuleVersion = '99.0'; PowerShellVersion = '99.0'; "
                "RootModule = 'ForeignSecurity.psm1' }\n",
                encoding="utf-8",
            )
            (module / "ForeignSecurity.psm1").write_text(
                "throw 'An incompatible security module was loaded'\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [POWERSHELL, "-NoLogo", "-NoProfile", "-Command",
                 "$ErrorActionPreference='Stop'; "
                 "Remove-Module Microsoft.PowerShell.Security -ErrorAction SilentlyContinue; "
                 "$env:PSModulePath=$env:XINGCHI_TEST_MODULE_ROOT+"
                 "[IO.Path]::PathSeparator+[IO.Path]::Combine($PSHOME,'Modules'); "
                 ". $env:XINGCHI_TEST_INSTALLER -Help; "
                 "Import-Module Microsoft.PowerShell.Security; "
                 "$module=Get-Module Microsoft.PowerShell.Security; "
                 "if (-not $module.ModuleBase.StartsWith($PSHOME)) { "
                 "throw 'Security module came from another PowerShell installation' }; "
                 "Write-Output 'HOST_MODULE_OK'"],
                env={**os.environ, "USERPROFILE": str(home),
                     "LOCALAPPDATA": str(home),
                     "XINGCHI_TEST_MODULE_ROOT": str(module_root),
                     "XINGCHI_TEST_INSTALLER": str(ROOT / "install.ps1")},
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("HOST_MODULE_OK", result.stdout)


@unittest.skipUnless(os.name == "nt", "the Windows installer only runs on Windows")
@unittest.skipUnless(POWERSHELL, "PowerShell is not installed")
class WindowsInstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)

        self.server = HTTPServer(("127.0.0.1", 0), _ModelsHandler)
        self.server.requests = []
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = "http://127.0.0.1:%d/v1" % self.server.server_address[1]

        # A stub keeps this test offline: without it the installer would run
        # "npm install -g @openai/codex" against the real npm prefix.
        fake_bin = self.home / "fakebin"
        fake_bin.mkdir()
        (fake_bin / "codex.cmd").write_text(
            '@echo off\nif "%~1"=="--version" (\n'
            '  echo codex-cli 0.170.0\n  exit /b 0\n)\n'
            'echo %*>"%XINGCHI_TEST_ARGS%"\n'
            'echo %XINGCHI_API_KEY%>"%XINGCHI_TEST_KEY%"\nexit /b 3\n'
        )

        self.env = dict(os.environ)
        self.env.update(
            {
                "USERPROFILE": str(self.home),
                "HOME": str(self.home),
                "CODEX_HOME": str(self.home / ".codex"),
                "XINGCHI_HOME": str(self.home / ".xingchi"),
                "XINGCHI_BIN": str(self.home / "bin"),
                # Padded on purpose: the installer trims pasted keys.
                "XINGCHI_API_KEY": "  " + KEY + "  ",
                "XINGCHI_ASTRA_API_KEY": "  " + ASTRA_KEY + "  ",
                "XINGCHI_UPSTREAM": self.base_url,
                # Never touch the developer's real PATH from a test.
                "XINGCHI_NO_PATH": "1",
                "PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
                "XINGCHI_TEST_ARGS": str(self.home / "args.txt"),
                "XINGCHI_TEST_KEY": str(self.home / "selected-key.txt"),
            }
        )
        self._result = None

    def install(self):
        if self._result is None:
            self._result = subprocess.run(
                [
                    POWERSHELL,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "install.ps1"),
                    "-Yes",
                ],
                env=self.env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
        self.assertEqual(
            self._result.returncode,
            0,
            "installer failed\nstdout:\n%s\nstderr:\n%s"
            % (self._result.stdout, self._result.stderr),
        )
        return self._result

    def test_key_never_lands_in_base_url(self):
        path_before = _user_path()
        self.install()
        self.assertEqual(
            path_before, _user_path(), "-NoPath must not rewrite the user PATH"
        )

        config = (self.home / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn('base_url = "%s"' % self.base_url, config)
        self.assertIn('env_key = "XINGCHI_API_KEY"', config)
        self.assertNotIn(KEY, config)

        # The specific failure that shipped: the key used as the base URL.
        for line in config.splitlines():
            if line.strip().startswith(("base_url", "model_catalog_url")):
                self.assertNotIn(KEY, line, "API key reached a URL: %s" % line)

        # The key belongs on the wire as a bearer header, not in the request
        # target (a key-as-URL produces a request for "<key>/models").
        self.assertEqual(
            [request["authorization"] for request in self.server.requests],
            ["Bearer " + KEY, "Bearer " + ASTRA_KEY],
        )
        self.assertTrue(all(request["path"] == "/v1/models" for request in self.server.requests))

        # The padded key was trimmed before it reached disk.
        key_file = (self.home / ".xingchi" / "upstream.key").read_text(encoding="utf-8")
        self.assertEqual(key_file, KEY + "\n")
        astra_file = (self.home / ".xingchi" / "astra.key").read_text(encoding="utf-8")
        self.assertEqual(astra_file, ASTRA_KEY + "\n")

    def test_installs_reasoning_catalog_with_all_levels(self):
        self.install()
        codex_home = self.home / ".codex"
        config = (codex_home / "config.toml").read_text(encoding="utf-8")
        catalog_path = codex_home / "xingchi-models.json"
        self.assertIn("model_catalog_json = " + json.dumps(str(catalog_path), ensure_ascii=False), config)
        self.assertNotIn("model_reasoning_effort", config)
        settings = tomllib.loads(config)
        self.assertNotIn("XingchiAstra", settings["model_providers"])
        self.assertEqual(settings["model_providers"]["OpenAI"]["capabilities"]["remote_compaction"], "unsupported")
        self.assertEqual(settings["features"], {
            "api_key_model_discovery": True, "image_generation": True, "goals": True,
        })
        models = json.loads(catalog_path.read_text(encoding="utf-8"))["models"]
        self.assertEqual([model["slug"] for model in models], ["gpt-6.1-sol"])
        astra_catalog = json.loads((codex_home / "xingchi-models-astra.json").read_text(encoding="utf-8"))["models"]
        self.assertEqual([model["slug"] for model in astra_catalog], [
            *json.loads((ROOT / "lib/model-groups.json").read_text(encoding="utf-8"))["astra"],
        ])
        astra_reasoning = next(model for model in astra_catalog if model["slug"] == "gpt-6-astra")
        self.assertEqual(
            [level["effort"] for level in astra_reasoning["supported_reasoning_levels"]],
            ["low", "medium", "high", "xhigh", "max", "ultra"],
        )
        self.assertEqual(
            [level["effort"] for level in models[0]["supported_reasoning_levels"]],
            ["low", "medium", "high", "xhigh", "max", "ultra"],
        )

    def test_launchers_do_not_contain_the_key(self):
        target = self.home / "bin"
        target.mkdir()
        payloads = ("xingchi-codex-runner.py", "xingchi_history.py", "xingchi_tui.py", "xingchi_conpty.py")
        for name in payloads:
            (target / name).write_text("# stale installation\n")
        self.install()

        launcher = (self.home / "bin" / "xingchi-codex.cmd").read_text(encoding="utf-8")
        status = (self.home / "bin" / "xingchi.cmd").read_text(encoding="utf-8")
        runner = (self.home / "bin" / "xingchi-codex-runner.py").read_text(encoding="utf-8")
        for name in payloads:
            self.assertEqual((target / name).read_bytes(), (ROOT / "bin" / name).read_bytes(),
                             f"The installer left an outdated {name}")
        for name in (*payloads, 'xingchi-codex.cmd', 'xingchi.cmd'):
            self.assertEqual((self.home / '.xingchi/bin' / name).read_bytes(), (target / name).read_bytes(),
                             f"The Xingchi runtime copy left an outdated {name}")

        self.assertIn('set "XINGCHI_UPSTREAM=%s"' % self.base_url, launcher)
        self.assertIn("upstream.key", runner)
        self.assertIn("astra.key", runner)
        self.assertIn("XINGCHI_RUNNER", launcher)
        self.assertIn("xingchi-codex-runner.py", launcher)
        self.assertIn(self.base_url, status)

        for name, text in (("xingchi-codex.cmd", launcher), ("xingchi.cmd", status),
                           ("xingchi-codex-runner.py", runner)):
            self.assertNotIn(KEY, text, "the API key leaked into %s" % name)
            self.assertNotIn(ASTRA_KEY, text, "the Astra key leaked into %s" % name)

    def test_launcher_forwards_model_effort_and_exit_code(self):
        self.install()
        launcher = self.home / "bin/xingchi-codex.cmd"
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(launcher), "-m", "gpt-6-luna",
             "-c", "model_reasoning_effort=max", "-a", "on-request", "-s",
             "read-only", "--approve-for-me", "--search"],
            env=self.env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        forwarded = (self.home / "args.txt").read_text().strip()
        self.assertEqual(
            forwarded,
            "--no-daemon -m gpt-6-luna -c model_reasoning_effort=max "
            "-a on-request -s read-only --approve-for-me --search",
        )
        self.assertEqual((self.home / "selected-key.txt").read_text().strip(), KEY)

    def test_launcher_astra_flag_selects_astra_key_and_default_model(self):
        self.install()
        launcher = self.home / "bin" / "xingchi-codex.cmd"
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(launcher), "--astra", "--search"],
            env=self.env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 3, result.stderr)
        forwarded = (self.home / "args.txt").read_text().strip()
        self.assertIn("model_catalog_json", forwarded)
        self.assertIn("xingchi-models-astra.json", forwarded)
        self.assertIn("-m gpt-6-astra", forwarded)
        self.assertIn("--search", forwarded)
        self.assertEqual((self.home / "selected-key.txt").read_text().strip(), ASTRA_KEY)

    def test_continue_forks_with_the_selected_key(self):
        self.install()
        launcher = self.home / "bin" / "xingchi-codex.cmd"
        for flags, key in (([], KEY), (["--astra"], ASTRA_KEY)):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    ["cmd.exe", "/d", "/c", str(launcher), *flags, "--continue", "--search"],
                    env=self.env, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 3, result.stderr)
                forwarded = (self.home / "args.txt").read_text().strip()
                self.assertIn("fork --last --search", forwarded)
                self.assertNotIn("--continue", forwarded)
                self.assertNotIn("-m ", forwarded, "Fork must preserve the previous model")
                self.assertEqual((self.home / "selected-key.txt").read_text().strip(), key)

    def test_reinstall_preserves_model_and_effort(self):
        self.install()
        path = self.home / ".codex/config.toml"
        (self.home / ".xingchi/models.txt").write_text("sol:gpt-6.1-terra\n", encoding="utf-8")
        text = path.read_text(encoding="utf-8").replace('model = "gpt-6.1-sol"', 'model = "gpt-6.1-terra"')
        path.write_text('model_reasoning_effort = "ultra"\n' + text, encoding="utf-8")
        self._result = None
        self.install()
        settings = tomllib.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(settings["model"], "gpt-6.1-terra")
        self.assertEqual(settings["model_reasoning_effort"], "ultra")
        self.assertEqual(settings["model_providers"]["OpenAI"]["capabilities"]["remote_compaction"], "unsupported")

    def test_incompatible_inherited_security_module_does_not_break_key_acls(self):
        # Reproduce pwsh -> Python -> powershell.exe with an incompatible
        # Microsoft.PowerShell.Security ahead of the host's bundled modules.
        module_root = self.home / "foreign-modules"
        module = module_root / "Microsoft.PowerShell.Security"
        module.mkdir(parents=True)
        (module / "Microsoft.PowerShell.Security.psd1").write_text(
            "@{ ModuleVersion = '99.0'; PowerShellVersion = '99.0'; "
            "RootModule = 'ForeignSecurity.psm1'; "
            "FunctionsToExport = @('Set-Acl', 'Get-Acl') }\n",
            encoding="utf-8",
        )
        (module / "ForeignSecurity.psm1").write_text(
            "throw 'An incompatible security module was loaded'\n",
            encoding="utf-8",
        )
        self.env["PSModulePath"] = str(module_root) + os.pathsep + self.env.get("PSModulePath", "")
        self.install()

        # Read the actual ACLs after setup; protection must never be skipped
        # merely to make installation succeed.
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-Command",
             "$ErrorActionPreference='Stop'; "
             "Import-Module ([IO.Path]::Combine($PSHOME, 'Modules', "
             "'Microsoft.PowerShell.Security', 'Microsoft.PowerShell.Security.psd1')); "
             "$paths=@('upstream.key','astra.key'); foreach ($name in $paths) { "
             "$acl=Get-Acl -LiteralPath ([IO.Path]::Combine($env:XINGCHI_HOME,$name)); "
             "if (-not $acl.AreAccessRulesProtected) { throw 'ACL inheritance enabled' }; "
             "$allowed=@([Security.Principal.WindowsIdentity]::GetCurrent().User.Value, "
             "'S-1-5-18', 'S-1-5-32-544'); "
             "foreach ($rule in $acl.Access) { "
             "$sid=$rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value; "
             "if ($sid -notin $allowed) { throw 'Unexpected ACL principal' } "
             "}; Write-Output $name }"],
            env=self.env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["upstream.key", "astra.key"])


if __name__ == "__main__":
    unittest.main()
