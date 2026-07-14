# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-14

Release correctness. Everything the README "what works today" table claims is now true when
exercised from a clean profile, and the guards that are supposed to keep it true actually check what
their names say they check. No architectural change: the deterministic retrieval core is still
planned, not shipped.

### Fixed

**Three guards that reported green while checking nothing.** The "fake form-field guard" only matched
an old markdown form-widget syntax, so it could not detect a command file with a missing or
mis-titled inputs section, and two such files were passing it. The tectonic install step was named
"checksum verified" and verified nothing: release 0.16.9 publishes no `SHA256SUMS` asset, so the
fetch was `|| true`-guarded and the verification branch was dead code. The release zip guard asserted
eleven leaf files but never asserted `skills/` or `.claude-plugin/`, so an over-matching exclude
pattern could have shipped an archive with no plugin in it.

**The Word-output skill told the model to run pandoc.** `skills/word-output/SKILL.md` described a
LaTeX-to-DOCX conversion path through pandoc, which is not in this repo and never has been, and its
frontmatter description (the field the plugin system routes on) advertised "Full DOCX with tracked
changes and comments" against a script that generates none of those. It now documents the real
`templates/word/build-docx.js` contract, and the seven capabilities it does not have are listed
together under a "Planned, not implemented" heading. The same overstatement is corrected in the
revision-management, cover-letter, response-to-reviewers, and latex-tables skills, and in three
README rows.

**The citation guard blocked commits it had no business blocking.** It scanned every `.tex` file in
the index whenever any `.tex` or `.bib` was touched, so a dangling citation in one manuscript blocked
a commit that only touched a different, unrelated manuscript. Scanning is now scoped to the
manuscript roots the commit actually touches. It also read bib keys with its own regex rather than
the brace-aware parser, which meant an `@comment{foo, bar}` block yielded a phantom key `foo` that
silently satisfied a `\cite{foo}` real BibTeX would reject; it now shares the parser, and strips
comments.

**Agent model routing was prose, not mechanism.** Five of the nine agents carried no `skills:`
preload at all. `visualization-agent` asserted that it routes code to a Sonnet subagent and plans
figures on Opus, when its own frontmatter pins it to Sonnet and none of its skills fork; the same
false claim appeared in `statistics-agent`. The prose now describes what actually happens.

**Journal lookup presented guesses as hits.** A query for a journal absent from the database returned
a different journal's full profile at exit 0 with no caveat (the script's own docstring example did
this). Fuzzy matches are now labeled as such, and separated from exact hits in JSON output.

**The PRISMA example could not be told from a real search.** Its flow counts carried no provenance
label, while the surrounding prose simultaneously called them illustrative and claimed the provenance
record held "the exact numbers for the run". They are illustrative, they are now labeled so, and the
docs page that asserted them as fact and called the search "reproducible" is corrected to match.

Also fixed: a hard 404 from the agents reference page to a skills catalog that did not exist,
`build-docx.js` dying with a raw `MODULE_NOT_FOUND` stack trace on a fresh clone, and two command
files missing their inputs section.

### Added

- `--check-duplicates` on `scripts/bib-validator.py`, so duplicate detection is selectable like every
  other check rather than always-on.
- Named per-entry DOI verdicts (`confirmed`, `no-doi`, `resolution-failed`): a resolved DOI is now
  stated as confirmed rather than passing in silence.
- `scripts/tests/fixtures/torture.bib`: nested braces, quoted values with commas and braces, bare
  macros, compact `}}` termination, and `@comment` / `@preamble` / `@string` blocks, all in one file.
- An explicit `Style:` invocation contract on the five visualization-family skills, with the
  precedence order stated once: explicit `Style:` line, then trigger phrase, then journal inference
  from `config.yaml`, then `default`.
- A skills catalog page in the docs reference section, covering all 29 skills.
- CI guards for the things that had none: honest command inputs, agent `skills:` preloads whose names
  must resolve, and unbacked `pandoc` / `docx-js` capability claims.
- 24 new tests (56 to 80), including the two the plan named and neither of which existed: a
  staged-only dangling citation with a clean worktree, and an unrelated manuscript that must not
  block.

### Changed

- The two `nature` example figures now use the palette `references/figure-styles.md` actually
  defines, so copying an example reproduces the shipped preset. Restyle only: every plotted number is
  unchanged, which matters because that data is the shared source of truth for the paired t-tests in
  `latex-results-table.md` and the confidence intervals in `response-to-reviewers.md`.
- CI pins Python in every job that uses it, enforces the committed npm lockfile with `npm ci`, and
  verifies the tectonic download against a pinned digest.
- The release workflow runs the test suite before it can publish a tag.

### Note on versioning

This release is 0.2.0, not the 0.2.2 the roadmap names. The 0.2.x numbers in the roadmap predate the
history rewrite that collapsed the never-public 0.2.x entries into 0.1.0, so shipping 0.2.2 as the
successor to 0.1.0 would imply two patch releases that never existed.

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
