#!/usr/bin/env python3
"""Freshness eval for the worked examples (and the LaTeX fixture).

Checks, per plans/06-examples-spec.md sections 5 and 6:

1. DOI resolution: every DOI found in examples/ resolves via the CrossRef API;
   every arXiv ID resolves via the arXiv export API.
2. LaTeX freshness: every fenced ```latex/```tex block is classified as
   standalone (contains \\documentclass; compiled directly) or fragment
   (wrapped in a minimal harness document first), then compiled. The generated
   fixture at evals/fixtures/manuscript-min/main.tex is compiled as a real
   multi-file manuscript.

Usage:
    python evals/example-freshness.py                     # everything
    python evals/example-freshness.py --skip-doi          # offline: LaTeX only
    python evals/example-freshness.py --skip-latex        # no TeX install: DOIs only
    python evals/example-freshness.py --engine latexmk    # pick the engine

Requires only the stdlib. Any TeX installation works: tectonic (on PATH or via
the TECTONIC variable), latexmk from TeX Live, MiKTeX, or MacTeX, or a raw
pdflatex, xelatex, or lualatex. Set LATEX_ENGINE to choose. Exits nonzero if any
check fails.
"""

import argparse
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from latex_engine import compile_document, find_engine, install_hint  # noqa: E402
USER_AGENT = "researcher-plugin-freshness-eval/0.2 (mailto:mareksokol98@gmail.com)"

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>\)\]\},;`|]+")
ARXIV_RE = re.compile(r"arXiv[:\s]+(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
FENCE_RE = re.compile(r"^```(latex|tex)\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL | re.IGNORECASE)
CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|autocite|textcite|parencite|footcite)"
    r"\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}"
)

HARNESS_PREAMBLE = r"""\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage{booktabs,multirow,threeparttable,array,tabularx}
\usepackage{xcolor,siunitx}
\usepackage{tikz}
\usetikzlibrary{positioning,arrows.meta,shapes.geometric,calc,fit,backgrounds,decorations.pathreplacing,shadows}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\usepackage[round]{natbib}
% Missing graphics must not fail a fragment compile: replace with a box.
% (renew: tikz already loads graphicx, so \includegraphics exists.)
\renewcommand{\includegraphics}[2][]{\fbox{graphic: \detokenize{#2}}}
"""

# Markers examples can carry (HTML comments, documented in plans/06-examples-spec.md):
#   <!-- freshness: expect-unresolvable <doi> -->  the DOI is a seeded fake and MUST NOT resolve
#   <!-- freshness: no-compile -->                 placed before a fence: skip compiling that block
EXPECT_UNRESOLVABLE_RE = re.compile(r"<!--\s*freshness:\s*expect-unresolvable\s+(\S+)\s*-->")
NO_COMPILE_RE = re.compile(r"<!--\s*freshness:\s*no-compile\s*-->\s*$")
INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
BIBLIOGRAPHY_RE = re.compile(r"\\bibliography\{([^}]+)\}")


def http_get(url, timeout=20):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def clean_doi(raw):
    return raw.rstrip(".,;:")


def collect_targets(md_files):
    """Return ({doi: [files]}, {arxiv_id: [files]}, [(file, index, kind, block)], {fake dois})."""
    dois, arxiv_ids, blocks, expected_unresolvable = {}, {}, [], set()
    for md in md_files:
        text = md.read_text(encoding="utf-8", errors="replace")
        for raw in EXPECT_UNRESOLVABLE_RE.findall(text):
            expected_unresolvable.add(clean_doi(raw))
        for raw in DOI_RE.findall(text):
            dois.setdefault(clean_doi(raw), []).append(md)
        for aid in ARXIV_RE.findall(text):
            arxiv_ids.setdefault(aid, []).append(md)
        for index, match in enumerate(FENCE_RE.finditer(text), start=1):
            preceding = text[: match.start()].rstrip()
            if NO_COMPILE_RE.search(preceding[-200:] if len(preceding) > 200 else preceding):
                blocks.append((md, index, "no-compile", ""))
                continue
            body = match.group(2).strip("\n")
            kind = "standalone" if "\\documentclass" in body else "fragment"
            blocks.append((md, index, kind, body))
    return dois, arxiv_ids, blocks, expected_unresolvable


def check_dois(dois, arxiv_ids, expected_unresolvable):
    failures = []
    for index, (doi, files) in enumerate(sorted(dois.items()), start=1):
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
        status = None
        for attempt in range(2):
            try:
                status, _ = http_get(url)
                break
            except urllib.error.HTTPError as err:
                status = err.code
                if status == 404:
                    break
            except (urllib.error.URLError, TimeoutError, OSError):
                status = None
            time.sleep(1.0)
        origin = ", ".join(sorted({f.name for f in files}))
        if doi in expected_unresolvable:
            # Seeded fake: it must KEEP failing to resolve, or the example is broken.
            if status == 404:
                print(f"  ok   DOI {doi} (seeded fake, correctly unresolvable)")
            else:
                failures.append(
                    f"Seeded fake DOI unexpectedly resolves (status {status}): {doi} (in {origin})"
                )
                print(f"  FAIL DOI {doi} -> seeded fake resolved with status {status} (in {origin})")
        elif status == 200:
            print(f"  ok   DOI {doi}")
        elif status == 404:
            failures.append(f"DOI does not resolve: {doi} (in {origin})")
            print(f"  FAIL DOI {doi} -> 404 (in {origin})")
        else:
            failures.append(f"DOI check errored (status {status}): {doi} (in {origin})")
            print(f"  FAIL DOI {doi} -> network/status {status} (in {origin})")
        time.sleep(0.05)

    for aid, files in sorted(arxiv_ids.items()):
        url = "http://export.arxiv.org/api/query?id_list=" + aid
        origin = ", ".join(sorted({f.name for f in files}))
        try:
            status, body = http_get(url)
            text = body.decode("utf-8", errors="replace")
            if status == 200 and "<entry>" in text and "Error" not in text[:2000]:
                print(f"  ok   arXiv:{aid}")
            else:
                failures.append(f"arXiv ID does not resolve: {aid} (in {origin})")
                print(f"  FAIL arXiv:{aid} (in {origin})")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as err:
            failures.append(f"arXiv check errored: {aid} ({err}) (in {origin})")
            print(f"  FAIL arXiv:{aid} -> {err} (in {origin})")
        time.sleep(0.2)
    return failures


def wrap_fragment(body):
    cite_keys = set()
    for match in CITE_RE.finditer(body):
        for key in match.group(1).split(","):
            key = key.strip()
            if key and "*" not in key:
                cite_keys.add(key)

    parts = [HARNESS_PREAMBLE, "\\begin{document}\n", body, "\n"]
    if cite_keys:
        parts.append("\\bibliographystyle{plainnat}\n\\bibliography{stub}\n")
    parts.append("\\end{document}\n")
    stub_bib = "".join(
        "@misc{%s,\n  author = {Stub, A.},\n  title = {Stub entry for compile check},\n  year = {2024},\n}\n"
        % key
        for key in sorted(cite_keys)
    )
    return "".join(parts), stub_bib


STUB_BIB_ENTRY = (
    "@misc{freshstub2024,\n  author = {Stub, A.},\n"
    "  title = {Stub entry for compile check},\n  year = {2024},\n}\n"
)


def stub_inputs(body, block_dir):
    """Create stubs for \\input/\\include targets and \\bibliography files so
    master-document blocks (whose section files live outside the example) compile.
    If the block runs BibTeX but cites nothing (all cites live in the stubbed
    sections), inject a \\nocite into a stub so the .bbl is never empty, which
    LaTeX would reject."""
    tex_stubs = []
    for name in INPUT_RE.findall(body):
        target = block_dir / (name if name.endswith(".tex") else name + ".tex")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text("% stub section for freshness compile check\n", encoding="utf-8")
            tex_stubs.append(target)
    has_bibliography = False
    for name in BIBLIOGRAPHY_RE.findall(body):
        for part in name.split(","):
            part = part.strip()
            target = block_dir / (part if part.endswith(".bib") else part + ".bib")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_text(STUB_BIB_ENTRY, encoding="utf-8")
                has_bibliography = True
    if has_bibliography and tex_stubs and not CITE_RE.search(body) and "\\nocite" not in body:
        tex_stubs[0].write_text(
            "% stub section for freshness compile check\n\\nocite{freshstub2024}\n",
            encoding="utf-8",
        )


def check_latex(blocks, fixture, engine):
    failures = []
    with tempfile.TemporaryDirectory(prefix="freshness-") as tmp:
        tmp_path = Path(tmp)
        for md, index, kind, body in blocks:
            if kind == "no-compile":
                print(f"  skip {md.relative_to(REPO_ROOT)} block {index} (marked no-compile)")
                continue
            name = f"{md.stem}-{index}"
            block_dir = tmp_path / name
            block_dir.mkdir()
            if kind == "standalone":
                (block_dir / "block.tex").write_text(body + "\n", encoding="utf-8")
                stub_inputs(body, block_dir)
            else:
                wrapped, stub_bib = wrap_fragment(body)
                (block_dir / "block.tex").write_text(wrapped, encoding="utf-8")
                if stub_bib:
                    (block_dir / "stub.bib").write_text(stub_bib, encoding="utf-8")
            ok, output, _ = compile_document(block_dir / "block.tex", engine=engine)
            label = f"{md.relative_to(REPO_ROOT)} block {index} ({kind})"
            if ok:
                print(f"  ok   {label}")
            else:
                tail = "\n".join(output.splitlines()[-25:])
                failures.append(f"LaTeX compile failed: {label}\n{tail}")
                print(f"  FAIL {label}")

    if fixture is not None:
        if fixture.exists():
            ok, output, _ = compile_document(fixture, engine=engine)
            if ok:
                print(f"  ok   fixture {fixture.relative_to(REPO_ROOT)}")
            else:
                tail = "\n".join(output.splitlines()[-25:])
                failures.append(f"Fixture compile failed: {fixture}\n{tail}")
                print(f"  FAIL fixture {fixture.relative_to(REPO_ROOT)}")
        else:
            failures.append(f"Fixture not found: {fixture}")
    return failures


def main():
    parser = argparse.ArgumentParser(description="Examples freshness eval (DOI + LaTeX)")
    parser.add_argument("--examples-dir", default=str(REPO_ROOT / "examples"))
    parser.add_argument("--fixture", default=str(REPO_ROOT / "evals" / "fixtures" / "manuscript-min" / "main.tex"))
    parser.add_argument("--skip-doi", action="store_true", help="skip DOI/arXiv resolution (offline)")
    parser.add_argument("--skip-latex", action="store_true", help="skip LaTeX compilation")
    parser.add_argument("--engine", help="tectonic, latexmk, pdflatex, xelatex, lualatex, "
                                         "or a path to an engine binary (default: autodetect)")
    args = parser.parse_args()

    examples_dir = Path(args.examples_dir)
    md_files = sorted(examples_dir.rglob("*.md"))
    if not md_files:
        print(f"No markdown files under {examples_dir}")
        return 1

    dois, arxiv_ids, blocks, expected_unresolvable = collect_targets(md_files)
    standalone = sum(1 for _, _, kind, _ in blocks if kind == "standalone")
    fragments = sum(1 for _, _, kind, _ in blocks if kind == "fragment")
    print(
        f"Scanned {len(md_files)} files: {len(dois)} unique DOIs ({len(expected_unresolvable)} "
        f"seeded fakes), {len(arxiv_ids)} arXiv IDs, {len(blocks)} LaTeX blocks "
        f"({standalone} standalone, {fragments} fragments, "
        f"{len(blocks) - standalone - fragments} no-compile)\n"
    )

    failures = []
    if args.skip_doi:
        print("DOI resolution: skipped (--skip-doi)")
    else:
        print("DOI and arXiv resolution:")
        failures += check_dois(dois, arxiv_ids, expected_unresolvable)

    if args.skip_latex:
        print("LaTeX freshness: skipped (--skip-latex)")
    else:
        try:
            engine = find_engine(args.engine)
        except FileNotFoundError as err:
            print(f"LaTeX freshness: FAILED, {err}")
            return 1
        if engine is None:
            print("LaTeX freshness: FAILED, no LaTeX engine found.\n")
            print(install_hint())
            failures.append("no LaTeX engine found; install one or pass --skip-latex")
        else:
            print(f"\nLaTeX freshness ({engine.name}: {engine.executable}):")
            failures += check_latex(blocks, Path(args.fixture) if args.fixture else None, engine)

    print()
    if failures:
        print(f"FAILED: {len(failures)} issue(s)")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("All freshness checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
