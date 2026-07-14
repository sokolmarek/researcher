#!/usr/bin/env python3
"""Install (or remove) the Researcher git pre-commit hook.

The Claude tool guard in hooks/hooks.json only sees commits that Claude itself
runs. This installer adds a real .git/hooks/pre-commit so commits made from a
terminal or IDE get the same dangling-\\cite check.

Usage (run from anywhere inside the target repository):
    python scripts/install-git-hooks.py             # install or refresh
    python scripts/install-git-hooks.py --uninstall # remove, restore prior hook

Behavior:
    - Idempotent: re-running refreshes the managed hook in place.
    - A pre-existing, unmanaged pre-commit is preserved as pre-commit.local and
      chained (it runs first; the citation check runs after it).
    - Fail-open: if python is not on PATH at commit time, the hook skips.
"""

import subprocess
import sys
from pathlib import Path

MARKER = "# researcher-plugin citation-check v1"
CHECK_SCRIPT = Path(__file__).resolve().parent / "citation-check-hook.py"

HOOK_TEMPLATE = """#!/bin/sh
{marker}
# Installed by scripts/install-git-hooks.py (Researcher plugin).
# Remove with: python "{installer}" --uninstall

if [ -f "$(dirname "$0")/pre-commit.local" ]; then
    sh "$(dirname "$0")/pre-commit.local" || exit 1
fi

PYTHON=$(command -v python || command -v python3)
if [ -z "$PYTHON" ]; then
    echo "researcher pre-commit: python not found, skipping citation check"
    exit 0
fi
"$PYTHON" "{check_script}" --git-hook
"""


def hooks_dir():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def to_posix(path):
    return str(path).replace("\\", "/")


def install(hooks):
    hooks.mkdir(parents=True, exist_ok=True)
    target = hooks / "pre-commit"
    if target.exists() and MARKER not in target.read_text(encoding="utf-8", errors="replace"):
        backup = hooks / "pre-commit.local"
        if backup.exists():
            print(f"Refusing to overwrite existing {backup}; merge your hooks manually.")
            return 1
        target.rename(backup)
        print(f"Existing pre-commit preserved as {backup} (it will run first).")

    target.write_text(
        HOOK_TEMPLATE.format(
            marker=MARKER,
            installer=to_posix(Path(__file__).resolve()),
            check_script=to_posix(CHECK_SCRIPT),
        ),
        encoding="utf-8",
        newline="\n",
    )
    try:
        target.chmod(0o755)
    except OSError:
        pass  # not meaningful on Windows
    print(f"Installed citation pre-commit hook at {target}")
    return 0


def uninstall(hooks):
    target = hooks / "pre-commit"
    if not target.exists():
        print("No pre-commit hook installed.")
        return 0
    if MARKER not in target.read_text(encoding="utf-8", errors="replace"):
        print(f"{target} was not installed by this script; leaving it alone.")
        return 1
    target.unlink()
    backup = hooks / "pre-commit.local"
    if backup.exists():
        backup.rename(target)
        print(f"Removed managed hook; restored previous hook from {backup.name}.")
    else:
        print("Removed managed pre-commit hook.")
    return 0


def main():
    hooks = hooks_dir()
    if hooks is None:
        print("Not inside a git repository (git rev-parse failed).")
        return 1
    if not CHECK_SCRIPT.exists():
        print(f"Cannot find {CHECK_SCRIPT}; is the plugin checkout complete?")
        return 1
    if "--uninstall" in sys.argv:
        return uninstall(hooks)
    return install(hooks)


if __name__ == "__main__":
    sys.exit(main())
