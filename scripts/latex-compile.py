#!/usr/bin/env python3
"""Compile a LaTeX manuscript with tectonic. Python twin of latex-compile.sh.

Usage:
    python scripts/latex-compile.py                       # manuscript/main.tex
    python scripts/latex-compile.py manuscript/main.tex   # specific file
    python scripts/latex-compile.py figures/diagram.tex   # standalone figure

Requires tectonic (https://tectonic-typesetting.github.io/). Looked up on PATH,
or set the TECTONIC environment variable to the binary. Runs tectonic from the
file's directory so \\input{} paths resolve. Exits nonzero on failure.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_tectonic():
    env = os.environ.get("TECTONIC")
    if env and Path(env).exists():
        return env
    return shutil.which("tectonic")


def main():
    tex_file = Path(sys.argv[1] if len(sys.argv) > 1 else "manuscript/main.tex")
    if not tex_file.is_file():
        print(f"Error: {tex_file} not found")
        return 1

    tectonic = find_tectonic()
    if tectonic is None:
        print("Error: tectonic is not installed (and TECTONIC is not set).")
        print("Install with one of:")
        print("  cargo install tectonic")
        print("  conda install -c conda-forge tectonic")
        print("  brew install tectonic")
        print("  or download a release binary: https://github.com/tectonic-typesetting/tectonic/releases")
        return 1

    workdir = tex_file.resolve().parent
    print(f"Compiling {tex_file}...")
    result = subprocess.run(
        [tectonic, tex_file.name, "--keep-intermediates", "--keep-logs"],
        cwd=workdir,
    )

    pdf = workdir / (tex_file.stem + ".pdf")
    if result.returncode == 0:
        print(f"Compiled successfully: {pdf}")
        return 0
    print(f"Compilation failed. Check {workdir / (tex_file.stem + '.log')} for details.")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
