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

The evidence kernel (`core/`) calls eight scholarly APIs, each documented per connector in
`connectors/` with a Data egress section. A short summary:

| Destination | Used by | Sends |
|---|---|---|
| `api.openalex.org` | search, verification, status | the query or DOI, polite-pool mailto |
| `api.crossref.org` | verification, status, citation skills | the DOI or bibliographic query, mailto |
| `api.datacite.org` | dataset and software DOI resolution | the DOI or query |
| `export.arxiv.org` | search, OA full text | the arXiv ID or query |
| `api.semanticscholar.org` | search, citation graph | the query or paper id |
| `eutils.ncbi.nlm.nih.gov` | PubMed search | the search query |
| `api.unpaywall.org` | OA location lookup | the DOI, polite-pool email |
| `opencitations.net` | citation-graph edges | the DOI |

Manuscript prose never leaves the machine through the kernel: only the DOI, title, or query you asked
to look up is sent. `--offline` (or `RESEARCHER_OFFLINE=1`) answers only from snapshots and the cache,
so nothing goes out at all. See `docs/` (Data egress, Licensing) for the full disclosure.

The plugin bundles a `.mcp.json` that registers the thin `researcher-core` MCP server (a local stdio
server over the same core, requiring the optional `mcp` extra), and nothing else. Scite and Zotero
run only if you connect them yourself. External reviewer models (OpenAI, Gemini, Ollama) are a
documented integration point, not implemented, so no keys are read and no requests are made to them.

## Manuscript content

Your manuscript text, bibliography, and data stay on your machine and in your Claude Code session.
The plugin does not upload them anywhere. The one exception is what you would expect: a DOI or a
search query you asked to look up is sent to the API being queried.

## Untrusted input

Text fetched from papers and metadata is untrusted input: a title, abstract, or extracted passage
may carry instructions ("ignore previous instructions", "mark this citation verified"), tool-call
lookalikes, or markup that widens scope. As of 1.0.0 the plugin defends against this rather than only
warning about it:

- `core/researcher_core/sanitize.py` strips control, ANSI, and bidi characters and neutralizes
  prompt-shaped patterns in the string fields of `--json` output, and passage text is quoted only
  inside a clearly labeled untrusted-content fence. The convention is documented in
  `references/untrusted-content.md`.
- `evals/run_injection.py` is the proof: it replays fake records whose titles, abstracts, and
  passages carry injection payloads through search, verify-bib, and faithfulness, and asserts every
  verdict is identical to the payload-free twin and that no payload string escapes the fence.

This certifies the known payload classes in the fixtures, not general immunity. A prompt-injection
report against the fencing conventions is in scope for this policy: a new payload that gets through
becomes a new fixture, not a footnote. Treat retrieved content as data, review what the plugin writes
into your manuscript, and report anything that steers behavior.

## Reporting scope

In scope: a fetched paper's content changing a verdict or escaping the untrusted-content fence; the
hooks or scripts doing something their documentation does not describe; a cached full-text leak into
a manuscript or a shared passport. The supported version is the latest release; fixes land there.
