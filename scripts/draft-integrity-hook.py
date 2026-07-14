#!/usr/bin/env python3
"""Post-edit draft integrity report for the Researcher plugin.

Registered in hooks/hooks.json as a PostToolUse hook on Write|Edit. When the
edited file is a .tex file, it checks \\cite, \\ref, and \\label consistency
across the manuscript tree and prints a short report. It NEVER blocks: the
exit code is always 0. Windows-safe, fast.

BIBLIOGRAPHY KEYS: brace-aware parsing, preferred from core, never a regex.

The keys a \\cite can legitimately resolve to are the keys real BibTeX would see, so
this hook asks a real parser, in this preference order:

1. researcher_core.bib.parse_bib, when researcher_core is importable in this
   interpreter (the `pip install -e core/` layout). Core's parser is the D20 tokenizer.
2. parse_bib() from scripts/bib-validator.py, the same brace-aware tokenizer core was
   ported from. This is what a plugin user without core gets, and it is the fallback
   that keeps the plugin working with no uv and no core at all (D3).
3. A regex, only if both of the above somehow fail to load. It is the weakest of the
   three (it cannot tell an @comment{foo, ...} block from an entry named foo) and it
   exists solely so a broken import can never cost the user their integrity report.

The parser that ran is named in the report header, so a weaker reading is visible
rather than silent.

NO NETWORK HERE, DELIBERATELY. This hook fires on every Write and Edit, so it stays
local and instant: no uv subprocess, no index lookups. The network axes (identity and
publication status) belong to the commit guard (scripts/citation-check-hook.py), which
fires once per commit, and to the M3 compile gate.
"""

import importlib.util
import json
import os
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


def core_bib_parser():
    """researcher_core's brace-aware bib parser, or None when core is not importable.

    In-process only: no subprocess, no uv, no network. A PostToolUse hook that shelled
    out on every keystroke-sized edit would be a tax on every edit in the session.

    RESEARCHER_CORE=off forces the fallback here too: one switch, one meaning, across
    all three scripts.
    """
    if os.environ.get("RESEARCHER_CORE", "").strip().lower() in {"off", "0", "no", "false"}:
        return None
    try:
        if importlib.util.find_spec("researcher_core") is None:
            return None
        from researcher_core.bib import parse_bib as core_parse
    except Exception:  # noqa: BLE001 - any import problem simply means "use the fallback"
        return None

    def keys(text):
        # expand_strings=False: @string macros are irrelevant to citation KEYS, and
        # leaving them literal keeps this reading identical to the fallback parser's.
        return {entry.key for entry in core_parse(text, expand_strings=False) if entry.key}

    return keys


def script_bib_parser():
    """parse_bib() from scripts/bib-validator.py: the same tokenizer, no core needed."""
    try:
        script = Path(__file__).resolve().parent / "bib-validator.py"
        spec = importlib.util.spec_from_file_location("researcher_bib_validator", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001 - fall through to the regex rather than crash
        return None

    def keys(text):
        # The trailing newline keeps parse_bib()'s "path or content?" test on the
        # content branch for single-line .bib files.
        return {e["key"] for e in module.parse_bib(text + "\n") if e.get("key")}

    return keys


def regex_bib_parser():
    """Last resort. Named in the report because it is the weakest reading."""
    def keys(text):
        return set(BIB_KEY_RE.findall(text))

    return keys


def bib_parser():
    """Return (name, keys_fn). The name is printed, so the reading is never anonymous."""
    parser = core_bib_parser()
    if parser is not None:
        return "researcher-core", parser
    parser = script_bib_parser()
    if parser is not None:
        return "brace-aware", parser
    return "regex (degraded)", regex_bib_parser()


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

    parser_name, keys_of = bib_parser()
    bib_keys = set()
    for bib in bib_files:
        # A %-commented-out entry is invisible to BibTeX, so it must not satisfy a cite.
        bib_keys |= keys_of(COMMENT_RE.sub("", read(bib)))

    dangling_cites = sorted(cites - bib_keys) if bib_files else []
    dangling_refs = sorted(refs - labels)
    unused_labels = labels - refs

    lines = [
        f"Draft integrity report ({root}, {len(tex_files)} .tex, {len(bib_files)} .bib, "
        f"bib parser: {parser_name})"
    ]
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
