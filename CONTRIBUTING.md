# Contributing

Issues and pull requests are welcome. If you are a researcher and something here wasted your time
rather than saving it, that is a bug worth filing.

## The one rule that is not negotiable

The plugin never fabricates a citation and never invents data. Every change must keep that true.
Nothing else in this document matters as much. The canonical statement is
[`references/integrity-constraints.md`](references/integrity-constraints.md), which is inlined into
every skill that produces cited content.

A corollary, and the reason several checks exist: **do not claim a capability the repository cannot
back.** If something is specified but not implemented, the docs must say so. An external review once
found this repo advertising four-index citation verification, DOCX tracked changes, and automatic
model routing, none of which existed. That is the failure mode this project takes most seriously.

## Development setup

```bash
git clone https://github.com/sokolmarek/researcher.git
cd researcher
claude --plugin-dir .                 # load the plugin from the working tree
python -m pip install pytest          # for the test suite
cd templates/word && npm install      # for the DOCX generator
```

A LaTeX engine is needed for the compile checks: tectonic, TeX Live, MiKTeX, or MacTeX all work
(see [`scripts/latex_engine.py`](scripts/latex_engine.py)).

## Before you open a pull request

```bash
claude plugin validate .claude-plugin/plugin.json     # manifest and components
python -m pytest scripts/tests                        # scripts and installers
python evals/example-freshness.py                     # every example DOI + LaTeX block
cd templates/word && npm test                         # DOCX generation
cd docs && npm run check && npm run build             # docs site
```

CI runs all of these, plus guards that will fail the build on:

- an em dash anywhere in tracked markdown, LaTeX, or JSON (house style, restructure the sentence);
- a bare `/command` form in user-facing docs (plugin commands are namespaced: `/researcher:sota`);
- a `(select: ...)` or `(toggle: ...)` field in a command file (there is no typed form UI);
- a leftover placeholder string.

## House conventions

- Each `SKILL.md` stays under 500 lines. Long content goes in `references/` and is loaded on demand.
- A skill's `description` carries its trigger phrases; that is how it gets matched.
- Skills cannot change the model with prose. Only `context: fork` plus `agent:` frontmatter does that.
- Examples in `examples/` contain only real, resolvable citations. The single permitted fake is the
  seeded entry in the citation-audit example, which exists to be caught, and the freshness eval fails
  if it ever starts resolving.
- Synthetic data is always labeled `(synthetic, for demonstration)`, and statistics are computed from
  real observations, never asserted. If a table shows significance stars, the input must contain the
  observations they were computed from.

## Adding a skill

1. `skills/<name>/SKILL.md` with `name` and `description` frontmatter (trigger phrases in the
   description).
2. If it produces cited content, data, LaTeX, or DOCX, inline the refusal-grade constraints and link
   `references/integrity-constraints.md`, as the existing skills do.
3. Update the counts in `README.md`, `CLAUDE.md`, and `.claude-plugin/plugin.json`.
4. If it should also work in Codex, nothing extra is needed: `scripts/install-codex-skills.py` picks
   up every skill automatically, and its test suite will tell you if a path fails to resolve.

## Roadmap

The direction is a measured, trustworthy core rather than a longer feature list: a deterministic
evidence kernel with published benchmarks, then an evidence-lineage compiler where every claim and
number in a manuscript traces back to a source span or an experiment run. See the roadmap page in the
[documentation](https://sokolmarek.github.io/researcher).
