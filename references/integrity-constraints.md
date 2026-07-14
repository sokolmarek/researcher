# Integrity Constraints (canonical runtime copy)

This file is the canonical copy of the Researcher plugin's integrity constraints. It exists because the
plugin-root `CLAUDE.md` is contributor documentation and is NOT loaded at plugin runtime. Skills and agents
that produce cited content, data, results, LaTeX, or DOCX must reference this file in their body AND inline
the refusal-grade constraints directly, because reference files load only when a skill reads them.

## Refusal-grade constraints

Violating any of these is never acceptable. When a task cannot proceed without violating one, stop, explain
which constraint applies, and ask the user how to proceed.

1. **Never fabricate citations.** Every reference must come from an actual retrieval (API response, MCP
   result, user-provided source). If a citation cannot be verified, say so; do not invent a DOI, author
   list, venue, year, or page range, and do not "fill in" plausible metadata from memory.
2. **Never invent data.** Results sections, tables, figures, and statistics describe only data the user
   actually provided or that was actually computed. Placeholder or illustrative numbers must be labeled
   `(synthetic, for demonstration)` and never presented as findings.
3. **Refusal classes.** Decline to present the following as valid output, and tell the user why:
   - a citation that is likely fabricated or cannot be resolved against any queried source;
   - a data claim that cannot be traced to user-provided data or an actual computation;
   - a source known to be retracted, unless the user explicitly wants to cite it as retracted.

## House constraints

4. **No em dashes in generated text.** Restructure the sentence: use commas, parentheses, colons, or two
   sentences instead.
5. **Compile-check all LaTeX before delivery** with tectonic (`scripts/latex-compile.py`, or
   `scripts/latex-compile.sh` on POSIX). Never deliver a `.tex` file that has not compiled.
6. **Validate DOCX before delivery.** Generated Word documents must open cleanly; run the generation
   script and confirm it exits without errors before handing the file over.
7. **Human-in-the-loop by default.** Verification verdicts, integrity flags, and refusal decisions are
   surfaced to the user for confirmation; the plugin does not silently drop or silently accept a suspect
   reference.

## How skills and agents use this file

- Link this file in the skill or agent body (for example: "Integrity constraints: see
  `references/integrity-constraints.md`; the refusal-grade rules below are binding").
- Inline constraints 1-3 (and whichever of 4-6 apply to the output type) in the skill or agent body so
  they are present in context even when this file is never read.
- Hooks provide a mechanical backstop for part of constraint 1 (`hooks/hooks.json`: a commit guard for
  dangling `\cite` keys and a post-edit integrity report). They complement, not replace, these rules.
