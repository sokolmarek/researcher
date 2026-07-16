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
3. Alt-text presence: every rendered example figure (an image under
   assets/img/examples/ referenced from examples/, including both dual-variant
   figures) carries non-empty alt text in its markdown ![alt](path). This is a
   mechanical presence check; alt-text quality stays a human checkpoint. It runs
   offline and is never skipped by --skip-doi or --skip-latex.

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

# Markdown image reference: ![alt](path). Alt text is group 1, target is group 2.
MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
# Rendered example figures live here; only images pointing into this directory
# are subject to the alt-text presence check (inline icons or badges are not).
EXAMPLE_ASSET_DIR = "assets/img/examples"


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
    """Returns (failures, network_warnings).

    The distinction is verdict versus ignorance. A 404 on a real DOI is a verdict (the
    citation is broken) and fails the gate. A timeout, a 5xx, or a rate limit says nothing
    about the citation, so it is a warning: an upstream hiccup must not block a merge or a
    release. The scheduled canary runs with --strict-network, where warnings fail too, so
    persistent unreachability still surfaces without gating every PR on Crossref uptime.
    """
    failures = []
    warnings = []
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
            elif status == 200:
                failures.append(
                    f"Seeded fake DOI unexpectedly resolves (status {status}): {doi} (in {origin})"
                )
                print(f"  FAIL DOI {doi} -> seeded fake resolved with status {status} (in {origin})")
            else:
                warnings.append(
                    f"Seeded fake DOI could not be checked (network/status {status}): {doi} (in {origin})"
                )
                print(f"  warn DOI {doi} -> network/status {status}, seeded fake unchecked (in {origin})")
        elif status == 200:
            print(f"  ok   DOI {doi}")
        elif status == 404:
            failures.append(f"DOI does not resolve: {doi} (in {origin})")
            print(f"  FAIL DOI {doi} -> 404 (in {origin})")
        else:
            warnings.append(f"DOI check errored (network/status {status}): {doi} (in {origin})")
            print(f"  warn DOI {doi} -> network/status {status} (in {origin})")
        time.sleep(0.05)

    for aid, files in sorted(arxiv_ids.items()):
        url = "http://export.arxiv.org/api/query?id_list=" + aid
        origin = ", ".join(sorted({f.name for f in files}))
        try:
            status, body = http_get(url)
            text = body.decode("utf-8", errors="replace")
            if status == 200 and "<entry>" in text and "Error" not in text[:2000]:
                print(f"  ok   arXiv:{aid}")
            elif status == 200:
                # arXiv answered and the ID is not there: that is a verdict, not an outage.
                failures.append(f"arXiv ID does not resolve: {aid} (in {origin})")
                print(f"  FAIL arXiv:{aid} (in {origin})")
            else:
                warnings.append(f"arXiv check errored (status {status}): {aid} (in {origin})")
                print(f"  warn arXiv:{aid} -> status {status} (in {origin})")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as err:
            warnings.append(f"arXiv check errored: {aid} ({err}) (in {origin})")
            print(f"  warn arXiv:{aid} -> {err} (in {origin})")
        time.sleep(0.2)
    return failures, warnings


def check_alt_text(md_files):
    """Presence check: every example figure (an image under assets/img/examples/
    referenced from examples/) carries non-empty alt text in its ![alt](path)
    markdown, and the referenced image file exists. Enforces presence only;
    alt-text quality is a human checkpoint in the review flow."""
    failures = []
    checked = 0
    for md in md_files:
        text = md.read_text(encoding="utf-8", errors="replace")
        for match in MD_IMAGE_RE.finditer(text):
            alt = match.group(1).strip()
            target = match.group(2).strip()
            norm = target.replace("\\", "/")
            if EXAMPLE_ASSET_DIR not in norm:
                continue
            checked += 1
            origin = md.relative_to(REPO_ROOT)
            image_name = norm.rsplit("/", 1)[-1]
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                failures.append(f"Example figure file missing: {image_name} (referenced in {origin})")
                print(f"  FAIL {image_name} -> referenced file not found (in {origin})")
                continue
            if not alt:
                failures.append(f"Example figure lacks alt text: {image_name} (in {origin})")
                print(f"  FAIL {image_name} -> empty alt text (in {origin})")
            else:
                print(f"  ok   {image_name} (alt text present, {len(alt)} chars, in {origin})")
    if checked == 0:
        failures.append(
            "No example figures found under assets/img/examples/; the alt-text "
            "presence check verified nothing (expected rendered example figures)"
        )
        print("  FAIL no example figures referenced under assets/img/examples/")
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
    parser.add_argument("--strict-network", action="store_true",
                        help="treat network errors as failures (scheduled canary mode); "
                             "by default they are non-gating warnings")
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

    # Alt-text presence runs offline and is never skipped: accessibility is a
    # release gate, not a network-dependent check.
    print("Alt-text presence (example figures under assets/img/examples/):")
    failures += check_alt_text(md_files)
    print()

    network_warnings = []
    if args.skip_doi:
        print("DOI resolution: skipped (--skip-doi)")
    else:
        print("DOI and arXiv resolution:")
        doi_failures, network_warnings = check_dois(dois, arxiv_ids, expected_unresolvable)
        failures += doi_failures
        if args.strict_network:
            failures += network_warnings
            network_warnings = []

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
    if network_warnings:
        print(f"WARNINGS (network, non-gating; the scheduled canary re-checks strictly): "
              f"{len(network_warnings)}")
        for warning in network_warnings:
            print(f"- {warning}")
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
