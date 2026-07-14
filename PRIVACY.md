# Privacy Policy

**Effective date:** 14 July 2026
**Applies to:** the Researcher plugin for Claude Code, Claude Cowork, and OpenAI Codex
**Maintainer:** Marek Sokol, <mareksokol98@gmail.com>

## Summary

Researcher collects nothing. It has no telemetry, no analytics, and no accounts. The maintainer
receives no data about you or your work, and cannot: the plugin is a set of skills and local scripts
that run on your machine, and nothing in it reports back.

Your manuscript, your bibliography, your data, and your figures stay on your machine. The plugin
never uploads them anywhere.

## What the plugin sends over the network, and when

The plugin makes outbound requests only when a skill or script you invoked needs data to do its job,
and only to public scholarly APIs. What is sent is the query itself: a DOI to resolve, a search term,
an author name, or an identifier. Nothing else is attached, and no identifier of you is attached.

| Destination | When | What is sent |
|---|---|---|
| `api.crossref.org` | validating a DOI, checking retractions, verifying a reference | the DOI being checked |
| `api.openalex.org` | literature search, verification | the search query or DOI |
| `api.semanticscholar.org` | literature search, author lookup | the query or author name |
| `export.arxiv.org` | literature search, preprint lookup | the arXiv ID or query |
| `eutils.ncbi.nlm.nih.gov` (PubMed) | literature search | the search query |

Each of these is an independent service with its own privacy policy, which governs what it does with
a request it receives. The plugin has no agreement with any of them and no special relationship: it
uses their public interfaces exactly as a browser would.

- Crossref: <https://www.crossref.org/operations-and-sundry/privacy/>
- OpenAlex: <https://openalex.org/privacy-policy>
- Semantic Scholar: <https://allenai.org/privacy-policy>
- arXiv: <https://info.arxiv.org/help/policies/privacy_policy.html>
- NCBI / PubMed: <https://www.nlm.nih.gov/web_policies.html>

If you never invoke a skill that searches or verifies, the plugin makes no network requests at all.

## What runs locally

- **Hooks** (active only while the plugin is enabled in Claude Code) read files in your repository and
  run read-only `git` commands, to check that your citations resolve. They write nothing and send
  nothing.
- **Scripts** you run yourself write only where you tell them to: `install-git-hooks.py` writes
  `.git/hooks/pre-commit` in your repository, and `install-codex-skills.py` writes into `~/.agents/`
  or a repository's `.agents/`. Both can be reversed with `--uninstall`.
- **LaTeX compilation** runs your local TeX engine on your local files.

See [SECURITY.md](SECURITY.md) for the full breakdown of what executes on your machine.

## What the plugin does not do

- It does not collect, store, or transmit your manuscript text, data, figures, or bibliography.
- It has no telemetry, usage analytics, crash reporting, or "anonymous statistics".
- It does not read, request, or transmit credentials or API keys. External reviewer models (OpenAI,
  Google, Ollama) are documented as a planned integration and are **not implemented**, so no keys are
  read and no requests are made to those services.
- It sets no cookies and hosts no service. The documentation site is static and served by GitHub
  Pages, which is subject to [GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## Things outside this plugin's control

- **Your AI assistant.** Claude Code, Claude Cowork, and OpenAI Codex send your conversation to their
  respective providers in order to work. That happens whether or not this plugin is installed, and it
  is governed by their policies, not this one. See Anthropic's
  [Privacy Policy](https://www.anthropic.com/legal/privacy) and OpenAI's
  [Privacy Policy](https://openai.com/policies/privacy-policy).
- **MCP servers you connect yourself.** If you connect Scite or a Zotero server, you do so with your
  own account, and that service's terms and privacy policy apply to what you send it. The plugin
  bundles no MCP servers and connects to none on your behalf.

## Children

The plugin is a developer and research tool and is not directed at children.

## Changes

Any change to this policy will be committed to the repository, so its history is public and
auditable. Material changes will be noted in [CHANGELOG.md](CHANGELOG.md).

## Contact

Questions about privacy, or a report that something here is inaccurate: <mareksokol98@gmail.com>, or
open an issue at <https://github.com/sokolmarek/researcher/issues>.
