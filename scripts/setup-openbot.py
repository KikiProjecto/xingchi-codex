#!/usr/bin/env python3
"""Connect a Linux OpenBot installation to the installed Xingchi launcher."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile


MARKER = "# Managed by xingchi-codex/scripts/setup-openbot.py"


def desktop_command(path: Path) -> str:
    # Desktop Exec fields have their own quoting rules; they are not shell code.
    value = str(path).replace("%", "%%")
    for character in ("\\", '"', "`", "$"):
        value = value.replace(character, "\\" + character)
    # The desktop file parser unescapes strings before parsing the Exec field.
    value = value.replace("\\", "\\\\")
    return '"' + value + '" %U'


def desktop_entry(text: str, launcher: Path) -> str:
    lines = text.splitlines()
    in_entry = False
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
        elif in_entry and line.startswith("Exec="):
            lines[index] = "Exec=" + desktop_command(launcher)
            replaced = True
        elif in_entry and line.startswith("TryExec="):
            lines[index] = "TryExec=" + str(launcher)
    if not replaced:
        raise ValueError("OpenBot desktop entry has no main Exec field")
    return "\n".join(lines) + "\n"


def setup(home: Path, openbot: Path, xingchi: Path, template: Path, apply: bool) -> list[Path]:
    for executable in (openbot, xingchi):
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError(f"executable missing: {executable}")
    skills = home / ".agents/skills"
    if not skills.is_dir():
        raise ValueError("shared ~/.agents/skills library missing; run the Xingchi installer first")

    bin_dir = home / ".local/bin"
    launcher = bin_dir / "openbot"
    provider = bin_dir / "xingchi-openbot-codex"
    if openbot.resolve() in (launcher.resolve(), provider.resolve()):
        raise ValueError("OpenBot executable must be the original application, not a generated launcher")
    if xingchi.resolve() in (launcher.resolve(), provider.resolve()):
        raise ValueError("Xingchi executable must be xingchi-codex, not a generated launcher")
    desktop = home / ".local/share/applications/openbot.desktop"
    source = desktop if desktop.is_file() else template
    entries = [
        (provider, "\n".join([
            "#!/bin/sh", MARKER,
            "exec " + shlex.quote(str(xingchi)) + " \\",
            "  -c 'model=\"gpt-6.1-sol\"' \\",
            "  -c 'sandbox_mode=\"danger-full-access\"' \\",
            "  -c 'approval_policy=\"never\"' \"$@\"", "",
        ]), 0o755),
        (launcher, "\n".join([
            "#!/bin/sh", MARKER,
            "export OPENBOT_CODEX_PATH=" + shlex.quote(str(provider)),
            "exec " + shlex.quote(str(openbot)) + ' "$@"', "",
        ]), 0o755),
        (desktop, desktop_entry(source.read_text(encoding="utf-8"), launcher), 0o644),
    ]
    # Validate every target before making any changes. Do not replace unrelated
    # command wrappers or write through a link into someone else's installation.
    for path, _, _ in entries:
        if path.is_symlink():
            raise ValueError(f"refusing to replace symbolic link: {path}")
        if path.exists() and (not path.is_file() or
                             path != desktop and MARKER not in path.read_text(encoding="utf-8")):
            raise ValueError(f"existing unmanaged launcher: {path}")
    changed = []
    for path, text, mode in entries:
        if path.is_file() and path.read_text(encoding="utf-8") == text and path.stat().st_mode & 0o777 == mode:
            continue
        changed.append(path)
        if not apply:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = path.with_name(path.name + ".xingchi.bak")
        if path.exists() and not backup.exists():
            shutil.copy2(path, backup)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        try:
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="install launchers; otherwise show planned changes")
    parser.add_argument("--openbot", type=Path, default=Path("/usr/bin/openbot"), help="original OpenBot executable")
    parser.add_argument("--xingchi", type=Path, default=Path.home() / ".local/bin/xingchi-codex")
    parser.add_argument("--desktop-template", type=Path, default=Path("/usr/share/applications/openbot.desktop"))
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("this setup command supports Linux desktop installations")
    try:
        changed = setup(Path.home(), args.openbot.absolute(), args.xingchi.absolute(), args.desktop_template, args.apply)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in changed:
        print(("installed: " if args.apply else "would update: ") + str(path))
    print("OpenBot Codex defaults: gpt-6.1-sol; full access; approval policy never")
    print("Shared skills: ~/.agents/skills (OpenBot and Codex read this library directly)")
    print("Restart OpenBot from its desktop entry or ~/.local/bin/openbot to use the launcher.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
