#!/usr/bin/env python3
"""Compile a LaTeX manuscript. Python twin of latex-compile.sh.

Usage:
    python scripts/latex-compile.py                        # manuscript/main.tex
    python scripts/latex-compile.py manuscript/main.tex    # a specific file
    python scripts/latex-compile.py figures/diagram.tex    # a standalone figure
    python scripts/latex-compile.py main.tex --engine latexmk
    python scripts/latex-compile.py main.tex --engine xelatex

Works with any TeX installation. It picks, in order: an engine you name
(--engine, or the LATEX_ENGINE environment variable), then tectonic (on PATH or
via the TECTONIC variable), then latexmk (TeX Live, MiKTeX, MacTeX), then a raw
pdflatex, xelatex, or lualatex with the BibTeX passes run explicitly.

Exits nonzero on failure.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from latex_engine import compile_document, find_engine, install_hint  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Compile a LaTeX document")
    parser.add_argument("tex_file", nargs="?", default="manuscript/main.tex",
                        help="path to the .tex file (default: manuscript/main.tex)")
    parser.add_argument("--engine", help="tectonic, latexmk, pdflatex, xelatex, lualatex, "
                                         "or a path to an engine binary")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="only print the engine's output on failure")
    args = parser.parse_args()

    tex_file = Path(args.tex_file)
    if not tex_file.is_file():
        print(f"Error: {tex_file} not found")
        return 1

    try:
        engine = find_engine(args.engine)
    except FileNotFoundError as err:
        print(f"Error: {err}")
        print()
        print(install_hint())
        return 1

    if engine is None:
        print(install_hint())
        return 1

    print(f"Compiling {tex_file} with {engine.name} ({engine.executable})...")
    ok, output, pdf = compile_document(tex_file, engine=engine)

    if ok:
        if not args.quiet and output.strip():
            print(output.strip()[-2000:])
        print(f"Compiled successfully: {pdf}")
        return 0

    print(output.strip()[-4000:])
    print(f"\nCompilation failed. Check {tex_file.with_suffix('.log')} for details.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
