#!/usr/bin/env python3
"""Install the Researcher skills for OpenAI Codex.

Codex implements the same open agent-skills standard as Claude Code: a skill is
a directory holding a SKILL.md with `name` and `description` frontmatter. Codex
scans, in priority order:

    $CWD/.agents/skills          repo scope (folder specific)
    $REPO_ROOT/.agents/skills    repo scope (shared with collaborators)
    $HOME/.agents/skills         user scope (all repos)

so all 35 skills port directly. What does NOT port is the Claude-specific
plumbing, and this installer handles each piece:

  * plugin-relative paths (`references/...`, `templates/...`, `scripts/...`,
    `${CLAUDE_PLUGIN_ROOT}`) are rewritten to absolute paths under a shared
    asset directory, because an installed Codex skill has no plugin root;
  * Claude-only frontmatter (`context: fork`, `agent:`, `model:`) is dropped,
    since Codex does not fork subagents; the affected skills keep working, they
    just run in the main session;
  * namespaced Claude commands (`/researcher:draft-section`) are rewritten to
    the Codex skill that command routed to (`$researcher-paper-drafting`);
  * the Claude tool guards in hooks/hooks.json have no Codex equivalent, so the
    installer points you at scripts/install-git-hooks.py, which installs a real
    git pre-commit hook that works with any agent (or none).

Usage:
    python scripts/install-codex-skills.py                 # user scope (~/.agents)
    python scripts/install-codex-skills.py --repo .        # repo scope (./.agents)
    python scripts/install-codex-skills.py --list          # what would be installed
    python scripts/install-codex-skills.py --uninstall

Stdlib only. Idempotent: re-running refreshes the installed copies.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PREFIX = "researcher-"

# Shared assets a skill may reference. Copied once, not per skill.
SHARED_DIRS = ("references", "templates", "scripts", "core")

# Claude-only frontmatter keys. Codex has no subagents to fork into.
CLAUDE_ONLY_KEYS = ("context", "agent", "model", "allowed-tools", "disallowed-tools")

# Claude commands route to skills; in Codex you invoke the skill directly.
COMMAND_TO_SKILL = {
    "new-manuscript": "manuscript-setup",
    "draft-section": "paper-drafting",
    "review-paper": "peer-review",
    "submit-ready": "journal-formatting",
    "revise": "revision-management",
    "brainstorm": "brainstorming",
    "find-journal": "journal-finder",
    "find-conference": "conference-finder",
    "fact-check": "fact-checking",
    "sota": "sota-finder",
    "design-experiment": "experiment-design",
    "research-pipeline": "research-pipeline",
    "verify-citations": "citation-audit",
    "systematic-review": "systematic-review",
    "watch-topic": "literature-monitoring",
}

# A plugin-relative path, but not one that is part of a longer path such as
# manuscript/references/library.bib (which belongs to the user's project).
ASSET_PATH_RE = re.compile(
    r"(?<![\w/.\-])(" + "|".join(SHARED_DIRS) + r")/([A-Za-z0-9_][A-Za-z0-9_./\-]*)"
)
PLUGIN_ROOT_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/?")
COMMAND_RE = re.compile(r"/researcher:([a-z-]+)")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

AGENTS_MD = """# Researcher

This project uses the Researcher skills for academic writing and literature work.

## Skills

The skills are installed under `{skills_root}` and are invoked either explicitly
(`$researcher-<name>`, for example `$researcher-literature-search`) or implicitly,
when what you ask for matches a skill's description. Run `/skills` to list them.

## Integrity rules (binding)

These are not style preferences. They are the point of the toolkit.

1. Never fabricate a citation. Every reference comes from an actual retrieval. If a
   citation cannot be verified, say so; do not invent a DOI, author, venue, or year.
2. Never invent data. Only user-provided or actually computed numbers appear as
   results. Anything illustrative is labeled "(synthetic, for demonstration)".
3. Refuse to present as valid: a likely-fabricated or unresolvable citation, a data
   claim with no traceable source, or a retracted source (unless the user is
   explicitly citing it as retracted).
4. No em dashes in generated prose. Use commas, colons, parentheses, or two sentences.
5. Compile-check LaTeX before delivering it: `python {shared}/scripts/latex-compile.py
   manuscript/main.tex` (works with tectonic, TeX Live, MiKTeX, or MacTeX).

The full text is at `{shared}/references/integrity-constraints.md`.

## Mechanical checks

Codex has no hook system, so the integrity guard runs as a real git hook instead.
Install it once in this repository:

    python {shared}/scripts/install-git-hooks.py

It blocks any commit whose `\\cite{{...}}` keys have no matching BibTeX entry,
including the case where a bibliography entry is deleted out from under a citation
that is already committed.

Validate a bibliography at any time:

    python {shared}/scripts/bib-validator.py manuscript/references/library.bib
"""


def skill_dirs():
    return sorted(p for p in (REPO_ROOT / "skills").iterdir() if (p / "SKILL.md").exists())


def targets(repo=None):
    """Return (skills_root, shared_root) for the requested scope."""
    base = Path(repo).resolve() / ".agents" if repo else Path.home() / ".agents"
    return base / "skills", base / "researcher"


# Sentences in a description that describe Claude-only routing. Codex matches skills
# on the description, so a claim about subagents there is both false and misleading.
CLAUDE_ROUTING_SENTENCE_RE = re.compile(
    r"\s*[^.\"]*\b(?:subagent|code-agent|Sonnet|Opus)\b[^.\"]*\.", re.IGNORECASE
)


def strip_claude_frontmatter(text):
    """Keep name and description; drop the keys Codex has no concept of."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return text, []
    kept, dropped = [], []
    for line in match.group(1).splitlines():
        key = line.split(":", 1)[0].strip()
        if key in CLAUDE_ONLY_KEYS:
            dropped.append(key)
        else:
            kept.append(line)

    if "context" in dropped or "agent" in dropped:
        kept = [
            CLAUDE_ROUTING_SENTENCE_RE.sub("", line) if line.startswith("description:") else line
            for line in kept
        ]

    body = text[match.end():]
    return "---\n" + "\n".join(kept) + "\n---\n" + body, dropped


CODEX_NOTE = (
    "> **Installed for Codex.** Under Claude Code this skill runs in a separate,\n"
    "> Sonnet-pinned subagent. Codex has no subagents, so it runs in the main session\n"
    "> instead. Ignore any mention below of forking or of the code-agent: the work is\n"
    "> the same, it just happens here.\n"
)


def rewrite(text, shared, note=False):
    """Make an installed skill self-consistent outside the plugin."""
    shared_posix = shared.as_posix()

    text = PLUGIN_ROOT_RE.sub(shared_posix + "/", text)

    def asset(match):
        # Only rewrite paths that are actually plugin assets. A skill also names
        # files it will CREATE in the user's project (scripts/train.py, for
        # example); those are not ours to rewrite.
        relative = f"{match.group(1)}/{match.group(2)}"
        probe = relative.rstrip(".,;:)`")
        if not (REPO_ROOT / probe).exists():
            return match.group(0)
        return f"{shared_posix}/{relative}"

    text = ASSET_PATH_RE.sub(asset, text)

    def command(match):
        skill = COMMAND_TO_SKILL.get(match.group(1))
        return f"${PREFIX}{skill}" if skill else match.group(0)

    text = COMMAND_RE.sub(command, text)

    if note:
        match = FRONTMATTER_RE.match(text)
        if match:
            text = text[:match.end()] + "\n" + CODEX_NOTE + text[match.end():]
        else:
            text = CODEX_NOTE + "\n" + text
    return text


def install(repo=None):
    skills_root, shared = targets(repo)
    skills_root.mkdir(parents=True, exist_ok=True)
    shared.mkdir(parents=True, exist_ok=True)

    for name in SHARED_DIRS:
        destination = shared / name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            REPO_ROOT / name, destination,
            # Skip test suites and every local tool cache: core/ ships its runnable package
            # and pyproject so `uv run --project <shared>/core` resolves on Codex, but its
            # virtualenv and caches are machine-local and must not travel.
            ignore=shutil.ignore_patterns(
                "tests", "__pycache__", "node_modules", "*.pyc",
                ".venv", ".pytest_cache", ".ruff_cache", ".mypy_cache",
            ),
        )

    installed, dropped_any = [], set()
    for source in skill_dirs():
        text = (source / "SKILL.md").read_text(encoding="utf-8")
        text, dropped = strip_claude_frontmatter(text)
        dropped_any.update(dropped)
        # A skill that forked into a subagent under Claude now runs inline: say so,
        # otherwise its own prose about the code-agent would mislead the model.
        forked = "context" in dropped or "agent" in dropped
        text = rewrite(text, shared, note=forked)

        destination = skills_root / f"{PREFIX}{source.name}"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "SKILL.md").write_text(text, encoding="utf-8")
        installed.append(destination.name)

    agents_md = shared / "AGENTS.md"
    agents_md.write_text(
        AGENTS_MD.format(skills_root=skills_root.as_posix(), shared=shared.as_posix()),
        encoding="utf-8",
    )

    print(f"Installed {len(installed)} skills into {skills_root}")
    print(f"Shared assets (references, templates, scripts) in {shared}")
    if dropped_any:
        print(f"Dropped Claude-only frontmatter keys: {', '.join(sorted(dropped_any))} "
              "(Codex has no subagents; those skills run in the main session)")
    print()
    print("Next steps:")
    print(f"  1. Copy the integrity rules into your project's AGENTS.md: {agents_md}")
    print(f"  2. Install the commit guard in each manuscript repo: "
          f"python {(shared / 'scripts' / 'install-git-hooks.py').as_posix()}")
    print("  3. In Codex, run /skills to list them, or invoke one directly, for example "
          f"${PREFIX}literature-search")
    return 0


def uninstall(repo=None):
    skills_root, shared = targets(repo)
    removed = 0
    if skills_root.exists():
        for path in skills_root.iterdir():
            if path.is_dir() and path.name.startswith(PREFIX):
                shutil.rmtree(path)
                removed += 1
    if shared.exists():
        shutil.rmtree(shared)
    print(f"Removed {removed} skills from {skills_root} and the shared assets in {shared}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Install the Researcher skills for Codex")
    parser.add_argument("--repo", nargs="?", const=".", default=None,
                        help="install into a repository's .agents/skills instead of ~/.agents/skills")
    parser.add_argument("--list", action="store_true", help="list the skills that would be installed")
    parser.add_argument("--uninstall", action="store_true", help="remove the installed skills")
    args = parser.parse_args()

    if args.list:
        skills_root, shared = targets(args.repo)
        print(f"Would install into {skills_root} (shared assets in {shared}):")
        for source in skill_dirs():
            print(f"  {PREFIX}{source.name}")
        return 0
    if args.uninstall:
        return uninstall(args.repo)
    return install(args.repo)


if __name__ == "__main__":
    sys.exit(main())
