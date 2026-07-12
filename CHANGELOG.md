# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-07-12

### Added
- Documentation site (Astro plus Starlight) with a full cookbook and worked showcases, deployed to GitHub Pages.
- `examples/` directory: 14 worked skill examples with real, DOI-verified output and rendered figures.
- `.claude-plugin/marketplace.json`, so the plugin installs via `/plugin install researcher@researcher-marketplace`.
- `CREDITS.md` acknowledging the projects that inspired this one.
- GitHub Actions: docs deployment to GitHub Pages, release automation on tags, and repository validation.
- Rendered example figures: the two-stage TikZ pipeline, the PlotNeuralNet CNN, the results table, and a label-efficiency chart.

### Changed
- Reworked the README voice: a tireless assistant that does not sleep so you can, not a co-author.
- Cleaned the plugin manifest: real author and repository metadata, and removed the unsupported `connectors` field.

### Fixed
- Placeholder author and homepage in the plugin manifest.

## [0.2.0] - 2026-06

### Added
- Initial plugin: 28 skills, 9 agents, 11 slash commands, connector docs, hooks, references, LaTeX and Word templates, and utility scripts.

[0.2.1]: https://github.com/sokolmarek/researcher/releases/tag/v0.2.1
[0.2.0]: https://github.com/sokolmarek/researcher/releases/tag/v0.2.0
