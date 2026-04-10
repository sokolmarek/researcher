#!/usr/bin/env bash
# Compile LaTeX manuscript using tectonic.
#
# Usage:
#   ./scripts/latex-compile.sh                          # compile manuscript/main.tex
#   ./scripts/latex-compile.sh manuscript/main.tex      # compile specific file
#   ./scripts/latex-compile.sh figures/diagram.tex       # compile standalone figure
#
# Requires: tectonic (https://tectonic-typesetting.github.io/)
#   Install: cargo install tectonic
#            OR: conda install -c conda-forge tectonic
#            OR: brew install tectonic

set -euo pipefail

TEX_FILE="${1:-manuscript/main.tex}"

if [ ! -f "$TEX_FILE" ]; then
    echo "Error: $TEX_FILE not found"
    exit 1
fi

# Check tectonic is installed
if ! command -v tectonic &> /dev/null; then
    echo "Error: tectonic is not installed."
    echo "Install with one of:"
    echo "  cargo install tectonic"
    echo "  conda install -c conda-forge tectonic"
    echo "  brew install tectonic"
    exit 1
fi

DIR=$(dirname "$TEX_FILE")
BASENAME=$(basename "$TEX_FILE" .tex)

echo "Compiling $TEX_FILE..."

# Run tectonic from the file's directory so \input{} paths resolve
cd "$DIR"
tectonic "$(basename "$TEX_FILE")" --keep-intermediates --keep-logs 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Compiled successfully: $DIR/$BASENAME.pdf"
else
    echo "✗ Compilation failed. Check $DIR/$BASENAME.log for details."
    exit 1
fi
