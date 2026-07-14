# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-14

First public release.

### Added

**The plugin.** 29 skills, 9 agents, and 11 namespaced slash commands (`/researcher:new-manuscript`
and friends) covering the research pipeline: brainstorming, literature search, research gaps,
experiment design, statistical analysis, implementation, manuscript drafting, visualization, citation
management, peer review, revision handling, journal and conference selection, and LaTeX or Word
formatting. Installs with `/plugin install researcher@researcher-marketplace`.

**Integrity you can check, not just promises.** The rules (never fabricate a citation, never invent
data) are inlined into every skill that produces cited content, and they are backed by mechanical
checks:

- A citation commit guard. It blocks a commit whose `\cite{...}` keys have no matching BibTeX entry,
  including the case where a bibliography entry is deleted out from under a citation that is already
  committed. It validates the prospective commit tree and scopes citations to the bibliographies each
  manuscript actually declares. `scripts/install-git-hooks.py` installs it as a real git pre-commit
  hook, so it also covers commits made from a terminal or an IDE.
- BibTeX validation (`scripts/bib-validator.py`): a brace-aware parser, CrossRef DOI resolution,
  title similarity and first-author matching, retraction flags, and duplicate detection. A 404 and a
  network failure are reported differently, because they mean different things.
- LaTeX compile checks that work with whatever TeX you have installed: tectonic, TeX Live, MiKTeX, or
  MacTeX (`scripts/latex_engine.py` resolves the engine; `--engine` or `LATEX_ENGINE` overrides).

**Figure style presets.** `default`, `nature`, and `ieee`, defined once in
`references/figure-styles.md` and shared by the visualization, TikZ, PlotNeuralNet, table, and
figure-suggestion skills. Ask for Nature style and the sizing, typography, and palette change; your
data does not.

**Word output.** `templates/word/build-docx.js` (Node plus the `docx` library) generates a formatted
DOCX from `sections/*.md`: title page, numbered headings, paragraphs, lists.

**Codex support.** `scripts/install-codex-skills.py` installs all 29 skills into `~/.agents/skills`
(or a repository's `.agents/skills`), rewriting plugin-relative paths so they resolve outside the
plugin and dropping the Claude-only routing that Codex has no concept of. Codex implements the same
open agent-skills standard, so the skills themselves port directly.

**Worked examples.** 15 examples with real, DOI-verified output and rendered figures, plus an eval
(`evals/example-freshness.py`) that resolves every DOI and compiles every LaTeX block, so the
examples cannot rot silently. The single fake citation in the set is seeded deliberately, and the
eval fails if it ever starts resolving.

**Documentation.** An Astro site with a cookbook and a per-skill reference, deployed to GitHub Pages,
plus a README that states plainly which capabilities work today and which are planned.

### Known limitations

Stated here because the alternative is pretending otherwise:

- Citation verification today means DOI resolution and retraction flags against CrossRef. Multi-index
  verification with four-state verdicts (verified, mismatch, unresolvable, inconclusive) is the next
  milestone, not a shipped feature.
- DOCX tracked changes, comments, and table emission are specified in
  `templates/word/article-imrad.md` but are not implemented.
- External reviewer models (OpenAI, Gemini, Ollama) are a documented integration point with no
  implementation. Peer review runs Claude's multi-persona panel.
- The journal database carries 16 publisher and journal profiles. Anything else is looked up from the
  publisher's author guidelines.
- Text fetched from papers is untrusted input, and hardened prompt-injection handling is planned work.
  See [SECURITY.md](SECURITY.md).

[0.1.0]: https://github.com/sokolmarek/researcher/releases/tag/v0.1.0
