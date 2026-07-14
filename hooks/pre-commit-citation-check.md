# Citation Commit Guard

Blocks a commit when a `\cite{key}` in a committed `.tex` file has no matching entry in any `.bib`
file in the repository. Coverage comes in two complementary layers, because a Claude tool guard only
sees commands that Claude itself runs:

| Layer | Covers | Registered by | Blocking behavior |
|---|---|---|---|
| Claude tool guard | `git commit` commands run by Claude | `hooks/hooks.json`, PreToolUse on `Bash` | exit code 2 blocks the tool call; stderr explains which keys are dangling |
| Git pre-commit hook | commits from a terminal or IDE | `python scripts/install-git-hooks.py` writes `.git/hooks/pre-commit` | exit code 1 aborts the commit |

Both layers run the same script: `scripts/citation-check-hook.py` (stdlib-only, Windows-safe).

## Trigger

- Guard: any Bash tool call whose command contains a `git commit`; all other commands exit 0 immediately.
- Git hook: every `git commit` in a repository where the hook is installed.

## What it checks

1. Runs only when the commit touches `.tex` or `.bib` files, but then validates EVERY `.tex` file in
   the index against the state being committed, so a bibliography-only deletion that strands
   already-committed citations is caught.
2. Content comes from the prospective commit tree: the index (`git show :path`), or the worktree for
   tracked files when the command uses `-a` (which stages tracked modifications at commit time).
   Untracked or unstaged `.bib` files never satisfy a citation, because they would not ship with the
   commit.
3. Citations are checked against the `.bib` files each manuscript actually declares: any directory
   whose `.tex` declares `\bibliography{...}` or `\addbibresource{...}` is a manuscript root, and
   every `.tex` under it validates against that root's declared bibliographies (with a repo-wide
   fallback only when nothing is declared).
4. Dangling keys block the commit, with the offending file named. Conservative by design: if the
   commit contains no `.bib` file at all, the guard warns instead of blocking; repositories with more
   than 500 `.tex` files skip the scan; and any internal error exits 0 (fail-open) so a guard bug can
   never lock you out of committing.

## Install and disable

- Full coverage: run `python scripts/install-git-hooks.py` once per manuscript repository. A
  pre-existing pre-commit hook is preserved as `pre-commit.local` and chained.
- Uninstall the git hook: `python scripts/install-git-hooks.py --uninstall`.
- Disable the Claude guard: remove the PreToolUse entry from `hooks/hooks.json` (or disable the plugin).

Deeper checks (uncited bib entries, missing DOIs, retractions) are not part of the commit guard; run
`python scripts/bib-validator.py <library.bib>` for those.
