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
- The check runs only when the commit touches .tex or .bib files, but it then
  validates EVERY .tex file in the index against the state being committed, so
  a bibliography-only deletion that strands already-committed citations is
  caught.
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
to every .bib in the index. When the repository has no .bib at all the guard
warns instead of blocking (conservative by design), and any internal error
exits 0 (fail-open) so a guard bug can never lock the user out of committing.
"""

import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|autocite|textcite|parencite"
    r"|footcite|smartcite|citeauthor|citeyearpar|citeyear|nocite)"
    r"\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}"
)
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s{}]+)\s*,")
BIB_DECL_RE = re.compile(r"\\(?:bibliography|addbibresource)\{([^}]+)\}")
COMMENT_RE = re.compile(r"(?<!\\)%.*")

MAX_TEX_FILES = 500


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


def commit_touches_bibliography(cwd, include_unstaged):
    changed = set(git_lines(["diff", "--cached", "--name-only", "--diff-filter=ACMDR"], cwd))
    if include_unstaged:
        changed |= set(git_lines(["diff", "--name-only", "--diff-filter=ACMDR"], cwd))
    return any(p.lower().endswith((".tex", ".bib")) for p in changed)


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


def check_commit(cwd, include_unstaged=False):
    """Return (dangling: {key: example_tex}, bib_count, tex_count, declared_missing)."""
    if not commit_touches_bibliography(cwd, include_unstaged):
        return {}, 0, 0, False

    tex_paths = [normalize(p) for p in git_lines(["ls-files", "--cached", "--", "*.tex"], cwd)]
    index_bibs = {normalize(p) for p in git_lines(["ls-files", "--cached", "--", "*.bib"], cwd)}
    if len(tex_paths) > MAX_TEX_FILES:
        print(
            f"researcher citation guard: {len(tex_paths)} .tex files exceeds the "
            f"{MAX_TEX_FILES}-file scan cap; skipping (not blocking).",
            file=sys.stderr,
        )
        return {}, 0, 0, False

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
        tex_dir = posixpath.dirname(tex_path)
        best_root, best_len = None, -1
        for root in roots:
            if (tex_dir == root or tex_dir.startswith(root + "/") or root == "") and len(root) > best_len:
                best_root, best_len = root, len(root)
        if best_root is not None:
            return roots[best_root]
        if all_declared:
            return all_declared
        return index_bibs

    bib_keys_cache = {}

    def keys_of(bib_path):
        if bib_path not in bib_keys_cache:
            text = prospective_content(bib_path, cwd, include_unstaged) or ""
            bib_keys_cache[bib_path] = set(BIB_KEY_RE.findall(text))
        return bib_keys_cache[bib_path]

    dangling = {}
    for path, text in tex_content.items():
        cited = set()
        for match in CITE_RE.finditer(text):
            cited |= split_keys(match.group(1))
        if not cited:
            continue
        known = set()
        for bib in bibs_for(path):
            known |= keys_of(bib)
        for key in cited - known:
            dangling.setdefault(key, path)

    return dangling, len(index_bibs), len(tex_content), declared_missing


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
        dangling, bib_count, tex_count, _ = check_commit(".", include_unstaged=False)
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
    dangling, bib_count, tex_count, _ = check_commit(cwd, include_unstaged=include_unstaged)
    report_and_exit(dangling, bib_count, tex_count, block_code=2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # fail-open: never break the commit workflow on a guard bug
        print(f"researcher citation guard: internal error, not blocking ({exc})", file=sys.stderr)
        sys.exit(0)
