#!/usr/bin/env python3
"""Launch Codex against Xingchi with an explicitly selected API key."""

from __future__ import annotations

import os
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tomllib

from xingchi_history import inherited_launch_args, inherit_command, local_history, read_thread, serve_history
from xingchi_tui import interactive_options, launch_directory, run_tui


DEFAULT_UPSTREAM = "https://api.xingchiapi.com/v1"


def home_dir() -> Path:
    return Path(os.environ.get("XINGCHI_HOME") or (Path.home() / ".xingchi"))


def read_key(filename: str) -> str:
    try:
        return (home_dir() / filename).read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""


def codex_command(args: list[str], model: str | None = None, group: str = "sol") -> list[str]:
    command = os.environ.get("XINGCHI_CODEX_BIN") or shutil.which("codex")
    if not command:
        raise RuntimeError("codex not found. Run the installer or install @openai/codex")
    full = [command, "--no-daemon"]
    if group == "astra":
        codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
        catalog_path = codex_home / "xingchi-models-astra.json"
        if catalog_path.is_file():
            full.extend(["-c", "model_catalog_json=" + json.dumps(str(catalog_path))])
    if model:
        full.extend(["-m", model])
    full.extend(args)
    if os.name == "nt" and Path(command).suffix.casefold() in {".cmd", ".bat"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", subprocess.list2cmdline(full)]
    return full


def catalog_models(group: str) -> set[str]:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    if group == "astra":
        catalog_path = codex_home / "xingchi-models-astra.json"
    else:
        try:
            config = tomllib.loads((codex_home / "config.toml").read_text(encoding="utf-8"))
            catalog_path = Path(config.get("model_catalog_json", codex_home / "xingchi-models.json"))
            if not catalog_path.is_absolute():
                catalog_path = codex_home / catalog_path
        except (OSError, ValueError):
            catalog_path = codex_home / "xingchi-models.json"
    try:
        entries = json.loads(catalog_path.read_text(encoding="utf-8")).get("models", [])
    except (OSError, ValueError):
        return set()
    return {item["slug"] for item in entries
            if isinstance(item, dict) and isinstance(item.get("slug"), str)}


def saved_model_is_valid_for_group(group: str) -> bool:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    try:
        model = tomllib.loads((codex_home / "config.toml").read_text(encoding="utf-8")).get("model")
    except (OSError, ValueError):
        return False
    if model not in catalog_models(group):
        return False
    # The history's Astra list overlaps the Sol model. A fresh Astra launch
    # should still begin on Astra rather than inherit that default.
    if group == "astra" and model in catalog_models("sol"):
        return False
    return True


def has_model_override(args: list[str]) -> bool:
    """Respect a model selected explicitly for this invocation."""
    for index, arg in enumerate(args):
        if arg in ("-m", "--model") and index + 1 < len(args):
            return True
        if arg.startswith("--model="):
            return True
        if arg in ("-c", "--config") and index + 1 < len(args):
            setting = args[index + 1].replace(" ", "")
            if setting.startswith("model="):
                return True
        if arg.startswith("--config=") and arg[len("--config="):].replace(" ", "").startswith("model="):
            return True
    return False


def run_codex(args: list[str]) -> int:
    use_astra = bool(args and args[0] == "--astra")
    if use_astra:
        args = args[1:]
    if args and args[0] in {"/inherit", "--inherit", "--inherit-history", "--serve-inherited-history"}:
        def app_server():
            return codex_command(["app-server", "--listen", "stdio://"])

        if args[0] == "--serve-inherited-history":
            if len(args) != 2:
                raise ValueError("expected one saved session ID")
            serve_history(args[1], app_server)
            return 0
        fresh_args = inherit_command(args, app_server, Path(__file__).resolve())
        if fresh_args is None:
            return 0
        args = fresh_args
    if args and args[0] == "--continue":
        # Fork through Codex itself: it copies saved conversation history and
        # allocates a new thread/session ID rather than resuming the capped ID.
        args = ["fork", "--last", *args[1:]]
    key_file = "astra.key" if use_astra else "upstream.key"
    api_key = read_key(key_file)
    if not api_key:
        group = "Astra" if use_astra else "GPT公益/Sol"
        print(f"error: {group} API key missing at {home_dir() / key_file}", file=sys.stderr)
        print("run the installer again and add your Xingchi key", file=sys.stderr)
        return 1

    child_env = os.environ.copy()
    child_env["XINGCHI_API_KEY"] = api_key
    child_env["OPENAI_API_KEY"] = api_key
    child_env["OPENAI_BASE_URL"] = os.environ.get("XINGCHI_UPSTREAM", DEFAULT_UPSTREAM).rstrip("/")
    child_env["XINGCHI_ACTIVE_GROUP"] = "astra" if use_astra else "sol"
    # Do not leave the other group's credential in Codex's inherited env.
    child_env.pop("XINGCHI_ASTRA_API_KEY", None)
    continuing_thread = bool(args and args[0] in {"resume", "fork"})
    group = "astra" if use_astra else "sol"
    initial_model = None
    if (not has_model_override(args) and not continuing_thread
            and not saved_model_is_valid_for_group(group)):
        initial_model = "gpt-6-astra" if use_astra else "gpt-6.1-sol"
    command = codex_command(args, model=initial_model, group=group)
    options = interactive_options(args)
    if options is not None and sys.stdin.isatty() and sys.stdout.isatty():
        cwd = launch_directory(args)

        def history_request():
            return local_history(codex_command(["app-server", "--listen", "stdio://"]), env=child_env)

        def fresh_command(id_: str, directory: Path) -> list[str]:
            with history_request() as request:
                read_thread(request, id_, directory)
            fresh_args = inherited_launch_args(id_, directory, Path(__file__).resolve(), options)
            return codex_command(fresh_args, model=initial_model, group=group)

        return run_tui(command, child_env, cwd, history_request, fresh_command)
    if os.name != "nt":
        os.execvpe(command[0], command, child_env)
    return subprocess.call(command, env=child_env)


def main(argv: list[str]) -> int:
    try:
        return run_codex(argv[1:])
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
