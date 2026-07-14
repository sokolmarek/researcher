# What this changes

<!-- One or two sentences. What problem does it solve? -->

## Checks

CI runs all of these, so it is faster to run them yourself first.

- [ ] `claude plugin validate .claude-plugin/plugin.json` passes
- [ ] `python -m pytest scripts/tests` passes
- [ ] `python evals/example-freshness.py` passes, if I touched `examples/` (every DOI resolves and every LaTeX block compiles)
- [ ] `cd docs && npm run check && npm run build` passes, if I touched `docs/`
- [ ] No em dashes anywhere in tracked markdown, LaTeX, or JSON
- [ ] Commands are written namespaced (`/researcher:sota`, never `/sota`)
- [ ] Any `SKILL.md` I touched is still under 500 lines

## Integrity

The project's one non-negotiable rule is that it never fabricates a citation and never invents data.

- [ ] This change does not make it easier to present an unverified claim as a verified one
- [ ] Any capability I documented actually works today, and anything planned is labeled as planned
- [ ] Any example data I added is labeled `(synthetic, for demonstration)`, and any statistic I show is
      computed from observations that are in the input, not asserted

## Anything reviewers should know

<!-- Tradeoffs, things you were unsure about, things you deliberately left out. -->
