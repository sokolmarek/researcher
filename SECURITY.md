# Security

## Reporting a vulnerability

Email <mareksokol98@gmail.com> with the details and a way to reproduce. Please do not open a
public issue for a security problem. You will get an acknowledgement within a few days.

## What this plugin executes on your machine

Being honest about this matters more than a badge, because the plugin ships hooks and scripts that
run locally.

**Hooks** (`hooks/hooks.json`, active only while the plugin is enabled in Claude Code):

- A PreToolUse guard on `Bash`. It inspects commands Claude is about to run, does nothing unless the
  command is a `git commit`, and then blocks the commit if a `\cite{...}` key has no matching BibTeX
  entry. It reads files, runs `git` read commands, and writes nothing.
- A PostToolUse hook on `Write|Edit`. When Claude edits a `.tex` file it prints a consistency report
  (dangling citations, dangling cross-references). It never blocks and writes nothing.

Both are stdlib-only Python, fail open (any internal error exits 0 rather than wedging your
workflow), and can be removed by deleting the entry from `hooks/hooks.json`.

**Scripts** you run yourself:

- `scripts/install-git-hooks.py` writes `.git/hooks/pre-commit` in the repository you run it in. It
  preserves any existing hook as `pre-commit.local` and chains it. Remove it with `--uninstall`.
- `scripts/install-codex-skills.py` writes into `~/.agents/` (or a repository's `.agents/`). Remove
  it with `--uninstall`.
- `scripts/bib-validator.py` and `evals/example-freshness.py` make outbound HTTPS requests (see
  below). `scripts/latex-compile.py` runs your local TeX engine.

## Network access

See [PRIVACY.md](PRIVACY.md) for the data-handling policy. In short: the plugin has no telemetry and
phones nothing home. Outbound requests happen only when a skill or
script you invoked needs data, and only to public scholarly APIs:

| Destination | Used by | Sends |
|---|---|---|
| `api.crossref.org` | `bib-validator.py`, freshness eval, citation skills | the DOI being checked |
| `export.arxiv.org` | freshness eval, literature search | the arXiv ID or query |
| `api.semanticscholar.org` | `scholar-scraper.py`, literature search | the author or paper query |
| `eutils.ncbi.nlm.nih.gov` | literature search (PubMed) | the search query |
| `api.openalex.org` | literature search, verification | the query or DOI |

MCP servers (Scite, Zotero) run only if you connect them yourself; the plugin bundles no
`.mcp.json`. External reviewer models (OpenAI, Gemini, Ollama) are specified but not implemented, so
no keys are read and no requests are made to them.

## Manuscript content

Your manuscript text, bibliography, and data stay on your machine and in your Claude Code session.
The plugin does not upload them anywhere. The one exception is what you would expect: a DOI or a
search query you asked to look up is sent to the API being queried.

## Untrusted input

Text fetched from papers and metadata is untrusted input. Hardened handling of it (prompt-injection
defenses, sanitization, fixtures) is planned work and is not yet implemented. Treat retrieved
content as data, not as instructions, and review what the plugin writes into your manuscript.
