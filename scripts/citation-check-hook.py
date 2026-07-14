#!/usr/bin/env python3
"""Citation commit guard for the Researcher plugin.

Two complementary entry points:

1. Claude tool guard (default, no flags): registered in hooks/hooks.json as a
   PreToolUse hook on Bash. Reads the hook payload JSON from stdin; if the
   command about to run is not a git commit, exits 0 immediately. Otherwise it
   validates the PROSPECTIVE COMMIT TREE and exits 2 to block the commit when a
   \\cite{key} would have no matching BibTeX entry in the committed state
   (stderr explains which keys dangle).

2. Git hook mode (--git-hook): installed as .git/hooks/pre-commit by
   scripts/install-git-hooks.py, covering commits made from a terminal or IDE.
   Same check; exit 1 blocks the commit.

What "prospective commit tree" means here:
- File content comes from the index (git show :path). For `git commit -a`,
  worktree content of tracked files is used instead, because -a stages tracked
  modifications at commit time (a file deleted from the worktree counts as
  deleted).
- Untracked or unstaged .bib files DO NOT satisfy citations: they would not be
  part of the commit.

Bibliography scoping: citations are checked against the .bib files each
manuscript actually declares. Any directory containing a .tex file with a
\\bibliography{...} or \\addbibresource{...} declaration is a manuscript root;
every .tex under that root validates against the union of the root's declared
bibliographies. A .tex outside any root falls back to all declared bibs, then
to every .bib in the index.

Scan scoping: the check runs only when the commit touches .tex or .bib files,
and it then scans every .tex under the MANUSCRIPT ROOTS the commit touched, not
just the changed files themselves. Scanning whole roots is deliberate: a
bibliography-only deletion strands citations in .tex files the commit never
touched, and a changed-files-only scan would miss them (the deleted bib lives
under the same root as the .tex files citing it, so root scoping still catches
it). Scoping to roots rather than to the whole index is equally deliberate: a
dangling key in an UNRELATED manuscript must not block a commit that only edits
this one. If a touched file belongs to no declared root, the scan widens to
every .tex in the index, which is the conservative fallback.

Bib keys come from parse_bib() in scripts/bib-validator.py, the one brace-aware
BibTeX parser in this repo, so the guard and the validator agree on what an
entry is. A regex would find keys inside @comment{...} blocks and inside
%-commented-out entries, and those phantom keys would silently satisfy \\cite
keys that real BibTeX would reject.

EVIDENCE REPORT (researcher-core, optional). When core is available (uv plus core/,
resolved by the core bridge in scripts/bib-validator.py) and the bibliographies in the
prospective commit carry DOIs, the guard also runs
`python -m researcher_core verify-bib --json` over the COMMITTED bibliography content
and prints what it found: axis (a) reference identity, and axis (b) publication status,
so a RETRACTED citation surfaces at commit time.

That report NEVER changes the exit code. What blocks a commit here is exactly what
blocked it before core existed: a citation key with no matching BibTeX entry in the
committed state. Retractions are REPORTED, NOT BLOCKED, at this stage, and so are the
refusal-grade identity findings (unresolvable, mismatch). The hard gate on those arrives
with the M3 compile gate and /researcher:submit-ready, which weigh a whole manuscript
rather than a single commit. Without core the guard behaves exactly as it did in M1
(proved by scripts/tests/test_core_fallback.py): the plugin never hard-fails when core
is absent (D3).

When the repository has no .bib at all the guard warns instead of blocking
(conservative by design), and any internal error exits 0 (fail-open) so a guard
bug can never lock the user out of committing. Fail-open cuts both ways: a bug
here stops guarding silently rather than erroring loudly, so every behavior
below is covered by a test that asserts a BLOCK.
"""

import importlib.util
import json
import posixpath
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|autocite|textcite|parencite"
    r"|footcite|smartcite|citeauthor|citeyearpar|citeyear|nocite)"
    r"\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}"
)
BIB_DECL_RE = re.compile(r"\\(?:bibliography|addbibresource)\{([^}]+)\}")
COMMENT_RE = re.compile(r"(?<!\\)%.*")

MAX_TEX_FILES = 500

# Bibliographies larger than this are not sent to core at commit time: a 900-entry
# library is a multi-minute verification, and a commit hook may not become that.
MAX_CORE_ENTRIES = 200

_VALIDATOR = None


def load_validator():
    """Return scripts/bib-validator.py as a module.

    It carries both the brace-aware parse_bib() and the core bridge (core_command,
    core_verify_bib, core_findings), so the guard, the validator, and the draft hook
    share one definition of "what is an entry" and one definition of "is core here".

    The filename has a hyphen, so it cannot be imported normally. Loading is lazy so
    that a missing or broken validator surfaces inside check_commit(), where the
    fail-open handler turns it into "not blocking" rather than a hard traceback.
    """
    global _VALIDATOR
    if _VALIDATOR is None:
        script = Path(__file__).resolve().parent / "bib-validator.py"
        spec = importlib.util.spec_from_file_location("researcher_bib_validator", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _VALIDATOR = module
    return _VALIDATOR


def load_parse_bib():
    """Return parse_bib() from scripts/bib-validator.py."""
    return load_validator().parse_bib


def bib_keys(text):
    """Citation keys a real BibTeX run would see in this .bib content.

    %-commented lines are stripped first, and @comment/@preamble/@string blocks are
    skipped by the parser, so neither can supply a key that satisfies a \\cite.
    """
    text = COMMENT_RE.sub("", text)
    # The trailing newline keeps parse_bib()'s "is this a path or is this content?"
    # test on the content branch for single-line .bib files.
    entries = load_parse_bib()(text + "\n")
    return {entry["key"] for entry in entries if entry.get("key")}


def run_git(args, cwd):
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def git_lines(args, cwd):
    out = run_git(args, cwd)
    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def changed_paths(cwd, include_unstaged):
    """Paths the prospective commit adds, changes, deletes, or renames."""
    changed = set(git_lines(["diff", "--cached", "--name-only", "--diff-filter=ACMDR"], cwd))
    if include_unstaged:
        changed |= set(git_lines(["diff", "--name-only", "--diff-filter=ACMDR"], cwd))
    return {normalize(p) for p in changed}


def prospective_content(path, cwd, include_unstaged):
    """Content of `path` as it would be committed, or None if it would be absent."""
    if include_unstaged:
        worktree = Path(cwd) / path
        if worktree.exists():
            try:
                return worktree.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
        return None  # deleted in the worktree; commit -a removes it
    text = run_git(["show", f":{path}"], cwd)
    if text is not None:
        return text
    try:
        return (Path(cwd) / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def split_keys(group):
    return {k.strip() for k in group.split(",") if k.strip() and "*" not in k}


def normalize(path):
    return posixpath.normpath(path.replace("\\", "/"))


def resolve_declaration(decl, tex_path, index_bibs):
    """Resolve one \\bibliography argument to index-relative .bib paths."""
    resolved = []
    for part in decl.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lower().endswith(".bib"):
            part += ".bib"
        tex_dir = posixpath.dirname(normalize(tex_path))
        candidates = [
            normalize(posixpath.join(tex_dir, part)) if tex_dir else normalize(part),
            normalize(part),  # repo-root relative
        ]
        for candidate in candidates:
            if candidate in index_bibs:
                resolved.append(candidate)
                break
    return resolved


def is_under(path, root):
    """True when `path` sits in directory `root` or below it (root "" is the repo root)."""
    directory = posixpath.dirname(path)
    return root == "" or directory == root or directory.startswith(root + "/")


def root_of(path, roots):
    """The longest declared manuscript root containing `path`, or None if there is none."""
    best, best_len = None, -1
    for root in roots:
        if is_under(path, root) and len(root) > best_len:
            best, best_len = root, len(root)
    return best


def check_commit(cwd, include_unstaged=False):
    """Inspect the prospective commit tree.

    Returns (dangling: {key: example_tex}, bib_count, tex_count, declared_missing,
    scoped_bibs: {bib_path: prospective_content}). The last element is the bibliography
    content the in-scope manuscripts actually declare, which is what the optional core
    evidence report reads: it must be the COMMITTED content, not the worktree file.
    """
    changed = changed_paths(cwd, include_unstaged)
    touched = {p for p in changed if p.lower().endswith((".tex", ".bib"))}
    if not touched:
        return {}, 0, 0, False, {}

    tex_paths = [normalize(p) for p in git_lines(["ls-files", "--cached", "--", "*.tex"], cwd)]
    index_bibs = {normalize(p) for p in git_lines(["ls-files", "--cached", "--", "*.bib"], cwd)}
    if len(tex_paths) > MAX_TEX_FILES:
        print(
            f"researcher citation guard: {len(tex_paths)} .tex files exceeds the "
            f"{MAX_TEX_FILES}-file scan cap; skipping (not blocking).",
            file=sys.stderr,
        )
        return {}, 0, 0, False, {}

    tex_content = {}
    for path in tex_paths:
        text = prospective_content(path, cwd, include_unstaged)
        if text is not None:
            tex_content[path] = COMMENT_RE.sub("", text)

    # Manuscript roots: directories whose .tex files declare bibliographies.
    roots = {}  # dir -> set of resolved bib paths (may be empty if declaration dangles)
    declared_missing = False
    for path, text in tex_content.items():
        decls = BIB_DECL_RE.findall(text)
        if not decls:
            continue
        root = posixpath.dirname(path)
        resolved = []
        for decl in decls:
            hits = resolve_declaration(decl, path, index_bibs)
            if not hits:
                declared_missing = True
            resolved.extend(hits)
        roots.setdefault(root, set()).update(resolved)

    all_declared = set().union(*roots.values()) if roots else set()

    def bibs_for(tex_path):
        root = root_of(tex_path, roots)
        if root is not None:
            return roots[root]
        if all_declared:
            return all_declared
        return index_bibs

    # Scan scope: every .tex under a manuscript root this commit touched. A .bib
    # deletion still maps to the root of the .tex files it stranded, so whole-root
    # scanning keeps that case working while an unrelated manuscript stays out of
    # scope. A touched file under no declared root widens the scan to everything.
    touched_roots, unscoped = set(), False
    for path in touched:
        root = root_of(path, roots)
        if root is None:
            unscoped = True
        else:
            touched_roots.add(root)

    if unscoped or not touched_roots:
        in_scope = tex_content
    else:
        in_scope = {
            path: text for path, text in tex_content.items()
            if any(is_under(path, root) for root in touched_roots)
        }

    bib_keys_cache = {}
    bib_text_cache = {}
    scoped_bibs = {}

    def text_of(bib_path):
        if bib_path not in bib_text_cache:
            bib_text_cache[bib_path] = prospective_content(bib_path, cwd, include_unstaged) or ""
        return bib_text_cache[bib_path]

    def keys_of(bib_path):
        if bib_path not in bib_keys_cache:
            bib_keys_cache[bib_path] = bib_keys(text_of(bib_path))
        return bib_keys_cache[bib_path]

    dangling = {}
    for path, text in in_scope.items():
        cited = set()
        for match in CITE_RE.finditer(text):
            cited |= split_keys(match.group(1))
        if not cited:
            continue
        known = set()
        for bib in bibs_for(path):
            scoped_bibs[bib] = text_of(bib)
            known |= keys_of(bib)
        for key in cited - known:
            dangling.setdefault(key, path)

    return dangling, len(index_bibs), len(in_scope), declared_missing, scoped_bibs


def core_evidence_report(scoped_bibs):
    """Print core's findings, and never let that reporting weaken the guard.

    The blocking check must survive anything the optional evidence layer does, so every
    failure inside it is contained here rather than reaching the module-level fail-open
    handler, which would exit 0 and let a dangling citation through.
    """
    try:
        _core_evidence_report(scoped_bibs)
    except Exception as exc:  # noqa: BLE001 - reporting must never break the guard
        print(
            f"researcher citation guard: evidence report skipped (internal error: {exc}). "
            "The citation-key check below is unaffected.",
            file=sys.stderr,
        )


def _core_evidence_report(scoped_bibs):
    """Print core's axis (a)/(b) findings for the committed bibliography content.

    Prints nothing when core is unavailable, when the bibliographies carry no DOI (there
    is nothing an index could resolve), or when the bibliography is too large to verify
    inside a commit. Every finding printed here is INFORMATION: this function has no say
    in the exit code, and its wording must never suggest otherwise.
    """
    if not scoped_bibs:
        return
    validator = load_validator()
    if validator.core_command() is None:
        return  # no uv, no core: the M1 behavior, silently

    combined = "\n\n".join(text for text in scoped_bibs.values() if text.strip())
    if not combined.strip():
        return
    entries = validator.parse_bib(combined + "\n")
    with_doi = [e for e in entries if e.get("doi")]
    if not with_doi or len(entries) > MAX_CORE_ENTRIES:
        return

    with tempfile.TemporaryDirectory(prefix="researcher-guard-") as tmp:
        staged = Path(tmp) / "committed.bib"
        staged.write_text(combined, encoding="utf-8")
        report = validator.core_verify_bib(staged)

    if report is None:
        print(
            "researcher citation guard: the researcher-core evidence check did not run "
            "(core unavailable, too slow, or too old for `verify-bib`); "
            "local citation checks only.",
            file=sys.stderr,
        )
        return

    findings = validator.core_findings(report)
    flagged = [
        f for f in findings
        if f["refusal_grade"] or f["status"] in ("retracted", "corrected", "expression-of-concern")
    ]
    if not flagged:
        return

    print(
        f"researcher citation guard: researcher-core evidence report over "
        f"{len(findings)} bibliography entr{'y' if len(findings) == 1 else 'ies'}. "
        "REPORTED, NOT BLOCKED: none of the findings below affect this commit's exit code.",
        file=sys.stderr,
    )
    for finding in sorted(flagged, key=lambda f: f["key"]):
        doi = f" {finding['doi']}" if finding["doi"] else ""
        status = finding["status"]
        if status in ("retracted", "corrected", "expression-of-concern"):
            # An axis (b) finding. The axis (a) verdict rides along rather than being
            # replaced by it: a reference can be perfectly verified AND retracted, and
            # collapsing the two axes into one label is the mistake D16 exists to stop.
            detail = f" (axis b; axis a: {finding['verdict']})"
            print(f"  {status}  [{finding['key']}]{doi}{detail}", file=sys.stderr)
        else:
            detail = f": {finding['reason']}" if finding["reason"] else ""
            print(
                f"  {finding['verdict']}  [{finding['key']}]{doi} (axis a){detail}",
                file=sys.stderr,
            )
    print(
        "  Retractions and refusal-grade identity findings are reported here for the "
        "human checkpoint. The hard gate on them is the M3 compile gate "
        "(/researcher:submit-ready), not this hook. This hook blocks on one thing only: "
        "a citation key with no matching BibTeX entry in the committed state.",
        file=sys.stderr,
    )


def report_and_exit(dangling, bib_count, tex_count, block_code):
    if not dangling:
        sys.exit(0)
    if bib_count == 0:
        print(
            f"researcher citation guard: {len(dangling)} \\cite key(s) across {tex_count} "
            ".tex file(s) but no .bib file in the commit; not blocking. "
            "Add a bibliography or ignore this warning.",
            file=sys.stderr,
        )
        sys.exit(0)
    shown = ", ".join(
        f"{key} ({tex})" for key, tex in sorted(dangling.items())[:15]
    )
    more = "" if len(dangling) <= 15 else f" (+{len(dangling) - 15} more)"
    print(
        "researcher citation guard: commit blocked. "
        f"{len(dangling)} \\cite key(s) would have no matching BibTeX entry in the "
        f"committed state: {shown}{more}. "
        "Add the missing entries to the declared bibliography (or remove the citations) and retry.",
        file=sys.stderr,
    )
    sys.exit(block_code)


def main():
    if "--git-hook" in sys.argv:
        dangling, bib_count, tex_count, _, scoped_bibs = check_commit(".", include_unstaged=False)
        core_evidence_report(scoped_bibs)
        report_and_exit(dangling, bib_count, tex_count, block_code=1)

    # Claude PreToolUse guard: payload arrives as JSON on stdin.
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command", "")
    if not re.search(r"\bgit\b[^|;&]*\bcommit\b", command):
        sys.exit(0)

    cwd = payload.get("cwd") or "."
    include_unstaged = bool(
        re.search(r"(?:^|\s)-[a-z]*a[a-z]*\b", command) or re.search(r"--all\b", command)
    )
    dangling, bib_count, tex_count, _, scoped_bibs = check_commit(
        cwd, include_unstaged=include_unstaged
    )
    # The evidence report runs BEFORE the verdict so its findings are visible whether or
    # not the commit is blocked, and so a reader sees the two as separate things: what
    # core found, then what actually blocked.
    core_evidence_report(scoped_bibs)
    report_and_exit(dangling, bib_count, tex_count, block_code=2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # fail-open: never break the commit workflow on a guard bug
        print(f"researcher citation guard: internal error, not blocking ({exc})", file=sys.stderr)
        sys.exit(0)
