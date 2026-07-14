#!/usr/bin/env python3
"""Post-edit draft integrity report for the Researcher plugin.

Registered in hooks/hooks.json as a PostToolUse hook on Write|Edit. When the
edited file is a .tex file, it checks \\cite, \\ref, and \\label consistency
across the manuscript tree and prints a short report. It NEVER blocks: the
exit code is always 0. Stdlib-only, Windows-safe, fast.
"""

import json
import re
import sys
from pathlib import Path

CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citealp|citealt|autocite|textcite|parencite"
    r"|footcite|smartcite|citeauthor|citeyearpar|citeyear|nocite)"
    r"\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}"
)
REF_RE = re.compile(r"\\(?:ref|eqref|pageref|autoref|cref|Cref|vref)\*?\{([^}]+)\}")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s{}]+)\s*,")
COMMENT_RE = re.compile(r"(?<!\\)%.*")

MAX_FILES = 400


def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_root(tex_path):
    """Walk up from the edited file looking for a manuscript root."""
    current = tex_path.parent
    for _ in range(6):
        if (current / "main.tex").exists() or (current / "config.yaml").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return tex_path.parent


def split_keys(group):
    return {k.strip() for k in group.split(",") if k.strip() and "*" not in k}


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path.lower().endswith(".tex"):
        return

    tex_path = Path(file_path)
    if not tex_path.exists():
        return

    root = find_root(tex_path)
    tex_files = sorted(root.rglob("*.tex"))[:MAX_FILES]
    bib_files = sorted(root.rglob("*.bib"))[:MAX_FILES]

    cites, refs, labels = set(), set(), set()
    for tex in tex_files:
        text = COMMENT_RE.sub("", read(tex))
        for match in CITE_RE.finditer(text):
            cites |= split_keys(match.group(1))
        for match in REF_RE.finditer(text):
            refs |= split_keys(match.group(1))
        for match in LABEL_RE.finditer(text):
            labels |= split_keys(match.group(1))

    bib_keys = set()
    for bib in bib_files:
        bib_keys |= set(BIB_KEY_RE.findall(read(bib)))

    dangling_cites = sorted(cites - bib_keys) if bib_files else []
    dangling_refs = sorted(refs - labels)
    unused_labels = labels - refs

    lines = [f"Draft integrity report ({root}, {len(tex_files)} .tex, {len(bib_files)} .bib)"]
    if not bib_files and cites:
        lines.append(f"  citations: {len(cites)} keys, no .bib file found to check against")
    else:
        lines.append(f"  citations: {len(cites)} keys, {len(dangling_cites)} dangling"
                     + (f" -> {', '.join(dangling_cites[:10])}" if dangling_cites else ""))
    lines.append(f"  cross-refs: {len(refs)} refs, {len(dangling_refs)} dangling"
                 + (f" -> {', '.join(dangling_refs[:10])}" if dangling_refs else ""))
    lines.append(f"  labels: {len(labels)} defined, {len(unused_labels)} unreferenced (info only)")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never block, never crash the edit flow
        print(f"draft integrity hook: internal error ({exc})", file=sys.stderr)
    sys.exit(0)
