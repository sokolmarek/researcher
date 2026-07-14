# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-07-14

A correctness release. An external review found that several documented capabilities did not match what
the code actually did, and that three integrity scripts were defective. Everything below is either fixed
or now labeled honestly as planned.

### Fixed
- **Command invocation was documented wrong.** Installed plugin commands are namespaced, so every
  user-facing reference now reads `/researcher:<command>` (README, docs site, command files, skills,
  examples). CI fails on a bare `/command` form.
- **The BibTeX parser could not read compact entries.** `scripts/bib-validator.py` used a regex that
  required the closing brace on its own line, so it parsed ZERO of the ten entries in the
  citation-audit example. It is now a brace-aware tokenizer handling nested braces, quoted and bare
  values, `@comment`/`@preamble`/`@string`, and compact `}}` termination. It also implements what it
  advertised: title similarity, first-author surname matching, `--check-doi` / `--check-retracted` /
  `--check-fields` (all on by default), and distinct reporting for a 404 versus a network error. The
  dead `--fix` flag was removed.
- **The citation guard could certify a broken commit.** It now validates the prospective commit tree
  (index content, or worktree content under `git commit -a`) rather than only staged `.tex` files, so
  deleting a bibliography entry that strands an already-committed citation is caught. Citations resolve
  against the `.bib` files each manuscript actually declares (`\bibliography`, `\addbibresource`), so an
  unstaged or unrelated `.bib` can no longer satisfy a staged citation.
- **Journal lookup parsed nothing.** Its field regex expected `**Field**:` while the database writes
  `**Field:**`, so every profile came back empty; five publishers documented at H2 were invisible, and
  `--list` demanded a positional argument. All fixed, and the false claim that the script searches
  publisher websites is gone (it searches the local database and tells you where to look next).
- **Example statistics were wrong.** The peer-review report's weighted score did not follow the skill's
  own rubric and did not add up (it now uses the canonical six dimensions and computes to 60.9). The
  results table asserted significance stars from a means-only CSV; the input now carries five per-seed
  observations per method and the stars come from paired t-tests actually computed over them, with t and
  p values stated. The rebuttal argued from overlapping marginal confidence intervals and now reasons
  from the paired-difference interval. The PRISMA example claimed all included works evaluate on PTB-XL,
  which its own SOTA example contradicts, and its provenance record is now labeled for what it is: an
  aggregate summary, not a replayable ledger. The fact-check report labeled a claim Unsupported while
  arguing it was Contradicted; it is now Contradicted, matching the skill's definitions.
- **`build-docx.js` did not exist** despite five references to it. It ships now.

### Added
- `templates/word/build-docx.js`: real DOCX generation (Node plus the `docx` library) producing a title
  page, numbered headings, paragraphs, and lists from `sections/*.md`, with a node test.
- Figure style presets (`references/figure-styles.md`): `default`, `nature`, and `ieee`, consumed by the
  visualization, tikz-diagrams, plotneuralnet, latex-tables, and figure-suggestions skills. Presets
  restyle only; they never touch your data. Two examples now show a default and a Nature variant of the
  same figure, both rendered.
- `image-prompt-crafting` skill (29 skills total): prompts for external image generators for conceptual
  illustrations, graphical abstracts, and cover art, with a hard refusal boundary against data and
  results figures and a mandatory AI-disclosure caption.
- `scripts/tests/`: a pytest suite covering the BibTeX parser (including the compact entries that used
  to fail), the citation guard (bibliography deletions, unrelated bib files, `commit -a`), and the
  journal database parser.
- `scripts/render-example-figures.py`: reproducible rendering of the example figure previews.
- Mechanical model routing: the implementation and code-analysis skills carry `context: fork` +
  `agent: code-agent`, so they actually execute on Sonnet instead of merely asking to.

### Changed
- CI is now reproducible and can catch these classes of defect: pinned Claude CLI and tectonic (with
  checksum verification) instead of unpinned `npm install -g` and `curl | sh`, a pytest job on Windows
  and Linux, a command-namespacing guard, a fake-form-field guard, a docs build and type check on pull
  requests, and a release that refuses to publish unless the tag matches `plugin.json` and the CHANGELOG,
  and unless every runtime file is inside the package.
- Docs and skills no longer overstate: external reviewer models, DOCX tracked changes, multi-index
  citation verification, and full-text style analysis are all labeled as planned or corrected to what
  the code does. Command files describe inputs as gathered conversationally, because plugin commands have
  no typed form UI.

## [0.2.1] - 2026-07-12

### Added
- Documentation site (Astro plus Starlight) with a full cookbook and worked showcases, deployed to GitHub Pages.
- `examples/` directory: 15 worked skill examples with real, DOI-verified output and rendered figures.
- `.claude-plugin/marketplace.json`, so the plugin installs via `/plugin install researcher@researcher-marketplace`.
- `references/integrity-constraints.md`: the canonical runtime copy of the integrity rules (the plugin-root
  CLAUDE.md is not loaded at plugin runtime), referenced and inlined by every skill and agent that produces
  cited content, data, LaTeX, or DOCX.
- Working hooks. `hooks/hooks.json` registers a citation guard that blocks Claude-run `git commit` commands
  containing dangling `\cite` keys, and a post-edit draft integrity report (`\cite`/`\ref`/`\label`
  consistency, never blocking). `scripts/install-git-hooks.py` installs a real git pre-commit for
  terminal and IDE commits; `scripts/citation-check-hook.py` and `scripts/draft-integrity-hook.py` are
  stdlib-only and Windows-safe.
- `scripts/latex-compile.py`: cross-platform twin of `latex-compile.sh`.
- `evals/example-freshness.py`: resolves every DOI and arXiv ID in `examples/` (the seeded fake entry must
  keep failing to resolve) and compiles every fenced LaTeX block with tectonic, classifying blocks as
  standalone versus fragment and wrapping fragments in a harness document. `evals/fixtures/manuscript-min/`
  is a generated multi-file manuscript fixture compiled as part of the eval.
- YAML frontmatter for all 9 agents (machine-readable model routing: the code, visualization, and
  formatting agents pin to Sonnet) and all 11 commands (descriptions and argument hints).
- `CREDITS.md` acknowledging the projects that inspired this one.
- GitHub Actions: docs deployment to GitHub Pages, release automation on tags, and a validation workflow
  that runs the official `claude plugin validate` on both manifests, parses all tracked JSON, enforces the
  em-dash and placeholder guards repo-wide, and runs the examples freshness eval. Releases now run
  validation before packaging.
- Rendered example figures: the two-stage TikZ pipeline, the PlotNeuralNet CNN, the results table, and a
  label-efficiency chart.

### Changed
- Reworked the README voice: a tireless assistant that does not sleep so you can, not a co-author.
- Cleaned the plugin manifest: real author and repository metadata; removed the unsupported `connectors`
  field and the `skills`, `commands`, and `agents` arrays (components are auto-discovered, and explicit
  arrays replace the scan). `claude plugin validate` passes both manifests.
- README now documents what works today versus what is planned, and describes the integrity rules honestly:
  prompt-level constraints inlined in skills and agents plus mechanical guards, with the deterministic
  verification core as the next planned milestone.
- Connector docs rewritten on a common template (what it provides, mechanism, install and env vars, used
  by, fallback when absent), honest about user-connected MCP versus direct API versus docs-only.
- Hook docs rewritten to describe the Claude-tool-guard versus git-hook coverage split.
- Removed all em dashes from skills, references, and templates (house style, now CI-enforced across all
  tracked markdown, LaTeX, and JSON).

### Fixed
- Placeholder author and homepage in the plugin manifest.
- Blank "Routes to skill" placeholders in the new-manuscript, draft-section, review-paper, and revise
  commands, and the blank directory reference in the citation hook doc.

## [0.2.0] - 2026-06

### Added
- Initial plugin: 28 skills, 9 agents, 11 slash commands, connector docs, hooks, references, LaTeX and Word templates, and utility scripts.

[0.2.2]: https://github.com/sokolmarek/researcher/releases/tag/v0.2.2
[0.2.1]: https://github.com/sokolmarek/researcher/releases/tag/v0.2.1
[0.2.0]: https://github.com/sokolmarek/researcher/releases/tag/v0.2.0
