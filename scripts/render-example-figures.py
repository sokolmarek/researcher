#!/usr/bin/env python3
"""Render the PNG previews used by examples/ and the docs site.

Authoring-time utility, not part of CI (CI compiles the LaTeX, it does not
rasterize). Extracts the fenced code blocks from the example files, renders
them, and writes the PNGs into assets/img/examples/ plus the docs mirror.

Usage:
    python scripts/render-example-figures.py                 # render everything
    python scripts/render-example-figures.py latex-results-table
    python scripts/render-example-figures.py --list

Toolchain (discovered at run time, all optional except the one you need):
    matplotlib (Agg)        for the plot figures
    tectonic                for the LaTeX figures (PATH or the TECTONIC env var)
    pdftoppm or PyMuPDF     to rasterize the compiled PDF
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets" / "img" / "examples"
DOCS_ASSETS = REPO_ROOT / "docs" / "src" / "assets" / "examples"
EXAMPLES = REPO_ROOT / "examples"

FENCE_RE = re.compile(r"^```(\w+)\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)

# name -> (example file, code language, which matching block (0-based), output png)
TARGETS = {
    "tikz-architecture": ("visualization-latex/tikz-architecture-diagram.md", "latex", 0, "tikz-architecture.png"),
    "tikz-architecture-nature": ("visualization-latex/tikz-architecture-diagram.md", "latex", 1, "tikz-architecture-nature.png"),
    "plotneuralnet-cnn": ("visualization-latex/plotneuralnet-cnn.md", "latex", 0, "plotneuralnet-cnn.png"),
    "latex-results-table": ("visualization-latex/latex-results-table.md", "latex", 0, "latex-results-table.png"),
    "label-efficiency-plot": ("visualization-latex/visualization-plot.md", "python", 0, "label-efficiency-plot.png"),
    "label-efficiency-plot-nature": ("visualization-latex/visualization-plot.md", "python", 1, "label-efficiency-plot-nature.png"),
}

# A table/figure float cannot be typeset in `standalone` (\caption needs a float),
# so fragments compile in `article` and the preview package crops to the float.
FRAGMENT_HARNESS = r"""\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{booktabs,multirow,threeparttable,array,tabularx}
\usepackage{amsmath,siunitx,xcolor,graphicx}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta,shapes.geometric,calc,fit,backgrounds}
\usepackage[active,tightpage,floats]{preview}
\begin{document}
%(body)s
\end{document}
"""


def find_tectonic():
    env = os.environ.get("TECTONIC")
    if env and Path(env).exists():
        return env
    return shutil.which("tectonic")


def blocks_of(example_rel, language):
    text = (EXAMPLES / example_rel).read_text(encoding="utf-8")
    return [
        body.strip("\n")
        for lang, body in FENCE_RE.findall(text)
        if lang.lower() in ({"latex", "tex"} if language == "latex" else {language})
    ]


def pdf_to_png(pdf, png, dpi=300):
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm:
        stem = png.with_suffix("")
        subprocess.run(
            [pdftoppm, "-png", "-r", str(dpi), "-singlefile", str(pdf), str(stem)],
            check=True, capture_output=True,
        )
        return True
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("  need pdftoppm or PyMuPDF to rasterize; install one of them")
        return False
    doc = fitz.open(pdf)
    doc[0].get_pixmap(dpi=dpi).save(str(png))
    doc.close()
    return True


def render_latex(body, png, tectonic):
    if tectonic is None:
        print("  tectonic not found (PATH or TECTONIC env var); skipping")
        return False
    with tempfile.TemporaryDirectory(prefix="render-") as tmp:
        work = Path(tmp)
        source = body if "\\documentclass" in body else FRAGMENT_HARNESS % {"body": body}
        tex = work / "figure.tex"
        tex.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [tectonic, "figure.tex", "--keep-logs"],
            cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            print("  tectonic failed:")
            print("\n".join((result.stdout + result.stderr).splitlines()[-12:]))
            return False
        return pdf_to_png(work / "figure.pdf", png)


def render_python(body, png):
    with tempfile.TemporaryDirectory(prefix="render-") as tmp:
        work = Path(tmp)
        script = work / "figure.py"
        script.write_text(body, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "figure.py"],
            cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            print("  python render failed:")
            print("\n".join((result.stdout + result.stderr).splitlines()[-12:]))
            return False
        produced = sorted(work.glob("*.png"))
        if not produced:
            print("  the block produced no .png (does it call savefig?)")
            return False
        shutil.copyfile(produced[0], png)
        return True


def main():
    parser = argparse.ArgumentParser(description="Render example figure previews")
    parser.add_argument("targets", nargs="*", help="target names (default: all)")
    parser.add_argument("--list", action="store_true", help="list target names")
    parser.add_argument("--dpi", type=int, default=300)
    args = parser.parse_args()

    if args.list:
        for name, (example, lang, index, png) in TARGETS.items():
            print(f"  {name:32s} {example} [{lang} block {index}] -> {png}")
        return 0

    names = args.targets or list(TARGETS)
    tectonic = find_tectonic()
    ASSETS.mkdir(parents=True, exist_ok=True)

    failures = []
    for name in names:
        if name not in TARGETS:
            print(f"unknown target: {name} (use --list)")
            failures.append(name)
            continue
        example, language, index, png_name = TARGETS[name]
        print(f"{name}: {example} [{language} block {index}]")
        found = blocks_of(example, language)
        if index >= len(found):
            print(f"  block {index} not present yet (found {len(found)}); skipping")
            continue
        png = ASSETS / png_name
        ok = (render_latex(found[index], png, tectonic) if language == "latex"
              else render_python(found[index], png))
        if not ok:
            failures.append(name)
            continue
        print(f"  wrote {png.relative_to(REPO_ROOT)}")
        if DOCS_ASSETS.exists():
            shutil.copyfile(png, DOCS_ASSETS / png_name)
            print(f"  synced {(DOCS_ASSETS / png_name).relative_to(REPO_ROOT)}")

    if failures:
        print(f"\nFAILED: {', '.join(failures)}")
        return 1
    print("\nAll requested figures rendered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
