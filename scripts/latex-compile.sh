#!/usr/bin/env bash
# Compile a LaTeX document with whichever TeX engine is installed.
#
# Usage:
#   ./scripts/latex-compile.sh                        # manuscript/main.tex
#   ./scripts/latex-compile.sh manuscript/main.tex    # a specific file
#   ./scripts/latex-compile.sh figures/diagram.tex    # a standalone figure
#   LATEX_ENGINE=latexmk ./scripts/latex-compile.sh manuscript/main.tex
#
# Engine preference: $LATEX_ENGINE, then tectonic (PATH or $TECTONIC), then
# latexmk (TeX Live, MiKTeX, MacTeX), then pdflatex with explicit BibTeX passes.
#
# Install one of:
#   tectonic  https://tectonic-typesetting.github.io  (single binary, fetches packages)
#   TeX Live  https://tug.org/texlive/
#   MiKTeX    https://miktex.org
#   MacTeX    https://tug.org/mactex/
#
# The Python twin (scripts/latex-compile.py) has the same behavior and also runs
# on Windows.

set -euo pipefail

TEX_FILE="${1:-manuscript/main.tex}"

if [ ! -f "$TEX_FILE" ]; then
    echo "Error: $TEX_FILE not found"
    exit 1
fi

DIR=$(dirname "$TEX_FILE")
BASENAME=$(basename "$TEX_FILE" .tex)
FILENAME=$(basename "$TEX_FILE")

pick_engine() {
    if [ -n "${LATEX_ENGINE:-}" ]; then
        echo "$LATEX_ENGINE"; return
    fi
    if [ -n "${TECTONIC:-}" ] && [ -x "${TECTONIC}" ]; then
        echo "$TECTONIC"; return
    fi
    for candidate in tectonic latexmk pdflatex xelatex lualatex; do
        if command -v "$candidate" >/dev/null 2>&1; then
            echo "$candidate"; return
        fi
    done
    echo ""
}

ENGINE=$(pick_engine)
if [ -z "$ENGINE" ]; then
    echo "No LaTeX engine found. Install tectonic, TeX Live, MiKTeX, or MacTeX,"
    echo "or set LATEX_ENGINE to the engine you want to use."
    exit 1
fi

echo "Compiling $TEX_FILE with $ENGINE..."
cd "$DIR"

case "$(basename "$ENGINE")" in
    tectonic*)
        "$ENGINE" "$FILENAME" --keep-intermediates --keep-logs
        ;;
    latexmk*)
        "$ENGINE" -pdf -interaction=nonstopmode -halt-on-error "$FILENAME"
        ;;
    *)
        # Raw engine: run it, resolve the bibliography, then settle references.
        "$ENGINE" -interaction=nonstopmode -halt-on-error "$FILENAME"
        if [ -f "$BASENAME.bcf" ] && command -v biber >/dev/null 2>&1; then
            biber "$BASENAME"
        elif grep -q '\\bibdata' "$BASENAME.aux" 2>/dev/null && command -v bibtex >/dev/null 2>&1; then
            bibtex "$BASENAME"
        fi
        "$ENGINE" -interaction=nonstopmode -halt-on-error "$FILENAME"
        "$ENGINE" -interaction=nonstopmode -halt-on-error "$FILENAME"
        ;;
esac

if [ -f "$BASENAME.pdf" ]; then
    echo "Compiled successfully: $DIR/$BASENAME.pdf"
else
    echo "Compilation failed: no $BASENAME.pdf produced. Check $DIR/$BASENAME.log."
    exit 1
fi
