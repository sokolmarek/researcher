---
description: Save a topic as a standing search and, on rerun, report only the papers that are new since last time
argument-hint: "<topic or monitor id>"
---

# /researcher:watch-topic

Set up or rerun a living-review watch: a saved search that surfaces only what is NEW since the last
run, not the whole result set again.

## Inputs (gathered conversationally)
- Topic or monitor id: the subject to watch, or the id of an existing saved search to rerun. If a
  `manuscript/monitoring.json` already holds a matching `monitor_id`, this is a rerun; otherwise
  Claude helps set a new watch up. State it in your message, or Claude asks.
- Strategies (new watch only): the exact per-database query strings to save (OpenAlex filter,
  PubMed term string, arXiv query). Claude drafts them with you and records them verbatim; it never
  invents a strategy you did not approve.
- Sources: which databases to monitor (default: openalex, crossref, arxiv). State it or Claude asks.

## Behavior
Routes to the literature-monitoring skill.

1. **New watch:** drafts the verbatim strategies conversationally, runs each once through core to
   establish the baseline, and writes `manuscript/monitoring.json` (strategies, seed `seen_ids`,
   `last_run`, `run_count`).
2. **Rerun:** reads the saved state via `monitor status`, re-executes every saved strategy verbatim
   through `search` (a live `--record` call whose snapshots make the rerun auditable offline),
   diffs the returned record ids against `seen_ids`, and reports ONLY the unseen records. An
   unreachable source is called out as incomplete, never reported as "no new papers" (D9).
3. **Feed the review:** the new records become a new screening batch under the same locked protocol
   (or an amendment if the criteria must change), appended to the ledger so the derived PRISMA
   counts update. Every record entering the included set is identity-checked; `inconclusive` is
   flagged for human review, never dropped.
4. **Advance state:** appends the new ids to `seen_ids` (monotonic, no reordering), advances
   `last_run` to this run's timestamp, and increments `run_count`.

No scheduler ships in the plugin: automate reruns with external cron, Windows Task Scheduler, or
Claude Code recurring tasks (`/loop`, `/schedule`). Without core, the watch degrades to MCP servers
or web search for the discovery call, is not snapshot-reproducible, and says so.
</content>
