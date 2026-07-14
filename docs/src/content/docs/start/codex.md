---
title: Use with Codex
description: Install the 29 Researcher skills in Codex, and know exactly what carries over.
sidebar:
  order: 3
---

## Why it works

Codex and Claude Code implement the same open agent-skills standard: a skill is a directory holding a `SKILL.md` whose frontmatter carries a `name` and a `description`. Nothing in that format is Claude-specific, so all 29 Researcher skills port straight across.

Codex looks for skills in three places, in priority order:

1. `$CWD/.agents/skills`
2. `$REPO_ROOT/.agents/skills`
3. `$HOME/.agents/skills`

## Install

Clone the repository, then run the installer:

```bash
git clone https://github.com/sokolmarek/researcher.git
cd researcher

# User scope: ~/.agents/skills
python scripts/install-codex-skills.py

# Repo scope: ./.agents/skills, for a single project
python scripts/install-codex-skills.py --repo .
```

Two more flags:

```bash
python scripts/install-codex-skills.py --list       # preview what would be installed
python scripts/install-codex-skills.py --uninstall  # remove the installed skills
```

## Invoking a skill

Skills install under a `researcher-` prefix, so `literature-search` becomes `researcher-literature-search`. In Codex you can call one explicitly:

```
$researcher-literature-search self-supervised learning for ECG classification
```

Or just describe what you want and let Codex match the skill from its description, the same way it works in Claude Code. Run `/skills` to list everything Codex can see.

## What carries over

| Carries over to Codex | Claude-only |
|---|---|
| All 29 skills | The 9 subagents. Codex has none, so the two skills that fork into the Sonnet code-agent under Claude simply run in the main session, and the installed copies say so. |
| Every Python script (bib-validator, latex-compile, install-git-hooks). They are agent-agnostic and run standalone, with no agent at all. | The in-session tool guards in `hooks/hooks.json`. Codex has no hook system. |
| The real git pre-commit citation guard | The namespaced slash commands. The installer rewrites each one to the skill it routed to, so `/researcher:draft-section` becomes `$researcher-paper-drafting`. |
| LaTeX compile checks, with any TeX engine | |
| The figure style presets | |

## Integrity in Codex

With no hook system, the backstop is the real git hook. Install it once per manuscript repository:

```bash
python scripts/install-git-hooks.py
```

That installs a git `pre-commit` that blocks commits containing dangling `\cite` keys, regardless of which agent made the commit, or whether an agent was involved at all.

The installer also writes an `AGENTS.md` template into the shared asset directory, carrying the integrity rules (never fabricate a citation, never invent data, no em dashes in generated text, compile-check LaTeX before delivery). Copy those rules into your project's own `AGENTS.md` so Codex reads them every session.

## Paths and refreshing

Skills ship with plugin-relative paths (`references/...`, `templates/...`, `scripts/...`, and the `CLAUDE_PLUGIN_ROOT` variable). The installer rewrites them to absolute paths under a shared asset directory (`~/.agents/researcher`), so an installed skill still resolves every reference, template, and script it points at. The installer's test suite asserts that every referenced file exists after install.

Re-run the installer any time to refresh an existing install against a newer checkout.
