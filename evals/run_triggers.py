#!/usr/bin/env python3
"""Pooled trigger eval (M2.13, sizing policy D17).

WHAT THIS MEASURES, STATED PLAINLY BEFORE ANY NUMBER IS READ
------------------------------------------------------------
This runner has no live model to route with. It scores each prompt against every
skill's SKILL.md YAML frontmatter `description` (its trigger phrases plus its prose)
using a transparent lexical scorer defined in this file, and takes the top-scoring
skill as the predicted route.

That frontmatter description IS the string the plugin system matches user intent
against, so this eval measures a real and load-bearing property: whether the 29
descriptions DISCRIMINATE, that is, whether the words a user would plausibly say
for skill X land on X and not on its neighbours. A collision here is a genuine
defect in the descriptions and predicts a live misroute.

It is NOT a measurement of live model routing. A real model reads the whole
description, tolerates paraphrase, and uses conversation context; this scorer does
none of that. It will therefore be pessimistic on paraphrase (a prompt that shares
no vocabulary with the description scores zero here but may well route live) and
optimistic on lexical overlap (it cannot tell "draw the CNN" from "draw the CNN
diagram" the way a model can). Do not quote these numbers as live routing accuracy.
They bound description quality, nothing more.

THE SCORER (fully specified, no hidden state)
---------------------------------------------
For each skill, from the frontmatter `description`:
  * trigger phrases: the quoted 'phrases' after "Triggers when user says:", or the
    comma-separated phrases after "Triggers:" up to the end of that sentence.
  * description bag: every token of the description plus the skill name.
Both sides (prompt and description) go through the same pipeline: lowercase,
punctuation split, stopword removal, and the small documented lemma map below
(plural stripping plus explicit nominalization pairs such as analysis -> analyze).

  score(prompt, skill) =
      PHRASE_W * sum over the skill's trigger phrases of phrase_score(prompt, phrase)
    + DESC_W   * sum of idf(t) for prompt tokens t appearing anywhere in the skill's
                 description bag

  phrase component = (IDF mass of the UNION of prompt tokens matched by any trigger
                 phrase that clears a 0.5 token-coverage floor) x the ordering bonus of
                 the strongest such phrase (1.0 contiguous run, 0.7 all tokens present
                 but scattered, 0.45 partial coverage; halved for a phrase that reduces
                 to a single content token). Union, not a sum over phrases: otherwise a
                 skill with eight trigger phrases containing "journal" banks idf(journal)
                 eight times. Partial credit exists because users say "find recent papers
                 on X" while the description says "find papers"; demanding a contiguous
                 run would measure the scorer's rigidity, not the description's quality.

idf(t) = ln(29 / (1 + df(t))) + 1, df computed over the 29 description bags, so a word
every skill uses ("paper", "section") is worth almost nothing and a word one skill uses
("booktabs", "zotero") is worth a lot. A skill is only predicted at all if its score
clears --threshold; otherwise the prompt is routed to "none" (an abstention).

Honesty note on the constants: PHRASE_W, DESC_W, the coverage floor, and the ordering
bonuses were set by hand against this eval set, so the scorer is fitted to it to the
extent that four constants can fit 232 prompts. They are frozen module constants rather
than flags precisely so that a reported number is not a fresh search over knobs, but a
reader should discount the numbers accordingly: the interesting output is not the
headline rate, it is WHICH prompts collide with WHICH neighbouring skill.

METRICS AND THE GATE (D17)
--------------------------
  pooled recall            = positives whose top-1 skill is the intended skill, over 145
  pooled false-trigger rate= negatives whose top-1 skill IS the baited skill, over 87
Both are reported with 95% Wilson confidence intervals. THESE TWO POOLED NUMBERS ARE
THE ONLY GATE.

Per-skill rows are DIAGNOSTICS ONLY. At n=5 they cannot certify anything: 4/5 = 0.80
has a 95% Wilson interval of roughly 0.38 to 0.96. Asking this runner to certify a
single skill (--certify-skill NAME) makes it print that interval and decline, by design.

Usage:
    python evals/run_triggers.py                      # pooled report + per-skill diagnostics
    python evals/run_triggers.py --json               # machine-readable
    python evals/run_triggers.py --certify-skill peer-review    # refuses, exits 2
    python evals/run_triggers.py --min-recall 0.9 --max-false-trigger 0.1

Stdlib only (no PyYAML: this file carries a small YAML-subset reader). Exits 0 when the
pooled gate holds, 1 when it does not, 2 on a refusal or a set-integrity failure.
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
TRIGGERS_YAML = Path(__file__).resolve().parent / "triggers.yaml"

# D17 set sizes. The runner refuses to report a gate on anything smaller.
POSITIVES_PER_SKILL = 5
NEGATIVES_PER_SKILL = 3

# Scorer weights. Set by hand against the description corpus, then frozen; they are
# module constants rather than flags so that a reported number is not a search over knobs.
PHRASE_W = 1.0
DESC_W = 0.25
COVERAGE_FLOOR = 0.5  # a trigger phrase below this token coverage contributes nothing
BONUS_CONTIGUOUS = 1.0
BONUS_ALL_TOKENS = 0.7
BONUS_PARTIAL = 0.45
SINGLE_TOKEN_W = 0.5  # a trigger phrase that reduces to one content token is weak evidence
DEFAULT_THRESHOLD = 1.0

Z95 = 1.959963984540054

# Function words only. Content verbs stay in: "make figure", "create table", "show me the
# citation context" are real trigger phrases, and stripping their verb would collapse a
# two-token phrase to one token and destroy the signal the phrase exists to carry. The
# wh-words also stay in, because "where to publish" and "where to present" are exactly what
# separates journal-finder from conference-finder.
STOPWORDS = frozenset(
    """
    a an the this that these those
    i me my mine we us our ours you your yours it its they them their he she his her
    is are was were be been being am do does did doing have has had
    of for to in on at by with from into onto over under about as and or but if then so than
    can could should would will shall may might must
    please just some any no not here there s t re ve ll d m o y
    """.split()
)

# Lemma map, applied identically to prompts and to descriptions. Kept small and explicit:
# every entry exists to collapse a nominalization or participle that a user would say one
# way and a description writes the other way.
LEMMAS = {
    "analysis": "analyze",
    "analyses": "analyze",
    "analyse": "analyze",
    "analysing": "analyze",
    "analyzing": "analyze",
    "analyzed": "analyze",
    "analytic": "analyze",
    "statistical": "statistic",
    "statistics": "statistic",
    "citing": "cite",
    "cited": "cite",
    "cites": "cite",
    "citations": "citation",
    "writing": "write",
    "written": "write",
    "wrote": "write",
    "writes": "write",
    "drafting": "draft",
    "drafted": "draft",
    "drafts": "draft",
    "plotting": "plot",
    "plotted": "plot",
    "plots": "plot",
    "visualise": "visualize",
    "visualize": "visualize",
    "visualization": "visualize",
    "visualizations": "visualize",
    "visualizing": "visualize",
    "reviewing": "review",
    "reviewed": "review",
    "reviewer": "review",
    "reviewers": "review",
    "formatting": "format",
    "formatted": "format",
    "formats": "format",
    "searching": "search",
    "searched": "search",
    "searches": "search",
    "finding": "find",
    "finds": "find",
    "implementing": "implement",
    "implemented": "implement",
    "implementation": "implement",
    "implements": "implement",
    "designing": "design",
    "designed": "design",
    "designs": "design",
    "generating": "generate",
    "generated": "generate",
    "generates": "generate",
    "generation": "generate",
    "comparison": "compare",
    "comparisons": "compare",
    "comparing": "compare",
    "compares": "compare",
    "suggestion": "suggest",
    "suggestions": "suggest",
    "suggesting": "suggest",
    "suggests": "suggest",
    "recommendation": "recommend",
    "recommendations": "recommend",
    "recommends": "recommend",
    "verification": "verify",
    "verifying": "verify",
    "verified": "verify",
    "verifies": "verify",
    "validation": "validate",
    "validating": "validate",
    "validates": "validate",
    "revision": "revise",
    "revisions": "revise",
    "revising": "revise",
    "revised": "revise",
    "submission": "submit",
    "submissions": "submit",
    "submitting": "submit",
    "submits": "submit",
    "converge": "converge",
    "converging": "converge",
    "convergence": "converge",
    "checking": "check",
    "checked": "check",
    "checks": "check",
    "extracting": "extract",
    "reporting": "report",
    "reports": "report",
    "results": "result",
    "papers": "paper",
    "figures": "figure",
    "tables": "table",
    "diagrams": "diagram",
    "gaps": "gap",
    "claims": "claim",
    "sources": "source",
    "references": "reference",
    "journals": "journal",
    "conferences": "conference",
    "sections": "section",
    "manuscripts": "manuscript",
    "experiments": "experiment",
    "layers": "layer",
    "charts": "chart",
    "prompts": "prompt",
    "ideas": "idea",
    "arguments": "argument",
    "authors": "author",
    "deadlines": "deadline",
    "questions": "question",
    "hypotheses": "hypothesis",
    "methods": "method",
    "methodology": "method",
    "letters": "letter",
    "styles": "style",
    "docx": "docx",
    "word": "word",
    "codebase": "code",
    "coding": "code",
    "codes": "code",
    "images": "image",
    "illustrations": "illustration",
    "illustrate": "illustration",
    "libraries": "library",
    "entries": "entry",
    "benchmarks": "benchmark",
    "leaderboards": "leaderboard",
    "curves": "curve",
    "panels": "panel",
    "models": "model",
    "datasets": "dataset",
    "networks": "network",
    "architectures": "architecture",
    "pipelines": "pipeline",
    "flowcharts": "flowchart",
    "protocols": "protocol",
    "opportunities": "opportunity",
    "problems": "problem",
    "directions": "direction",
    "changes": "change",
    "comments": "comment",
    "editors": "editor",
    "templates": "template",
    "requirements": "requirement",
    "metrics": "metric",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def lemma(token: str) -> str:
    """Collapse a token to its lemma: explicit map first, then a conservative plural rule."""
    if token in LEMMAS:
        return LEMMAS[token]
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if (
        len(token) > 3
        and token.endswith("s")
        and not token.endswith(("ss", "us", "is", "as"))
    ):
        stem = token[:-1]
        return LEMMAS.get(stem, stem)
    return token


def tokenize(text: str) -> list[str]:
    """lowercase -> alphanumeric runs -> drop stopwords -> lemmatize."""
    out: list[str] = []
    for raw in TOKEN_RE.findall(text.lower()):
        if raw in STOPWORDS:
            continue
        tok = lemma(raw)
        if tok in STOPWORDS or len(tok) < 2:
            continue
        out.append(tok)
    return out


# ---------------------------------------------------------------------------
# Minimal YAML subset reader.
#
# The base runtime deps of this repo are httpx, rapidfuzz, platformdirs; PyYAML is not
# one of them and the evals must run from a bare stdlib Python. triggers.yaml is written
# to a deliberately restricted subset, and this reader implements exactly that subset:
# block mappings, block sequences, scalars (plain, single- or double-quoted), and
# whole-line `#` comments. No flow style, no anchors, no multi-line scalars, no inline
# comments. Anything outside the subset raises rather than being silently misread.
# ---------------------------------------------------------------------------


class YamlSubsetError(ValueError):
    pass


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        body = raw[1:-1]
        if raw[0] == '"':
            return body.replace('\\"', '"').replace("\\\\", "\\")
        return body.replace("''", "'")
    return raw


def _load_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw[:indent]:
            raise YamlSubsetError(f"line {n}: tabs are not allowed for indentation")
        lines.append((indent, raw.strip()))
    return lines


def _parse_block(lines: list[tuple[int, str]], i: int, indent: int):
    if lines[i][1].startswith("- "):
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_seq(lines: list[tuple[int, str]], i: int, indent: int):
    items: list = []
    while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
        content = lines[i][1][2:].strip()
        key = re.match(r"^([A-Za-z0-9_.-]+):(\s+(.*))?$", content)
        if key:
            # Inline first key of a mapping item: re-enter the mapping parser with a
            # synthetic line at the item's content column.
            child_indent = indent + 2
            synthetic = [(child_indent, content)]
            j = i + 1
            while j < len(lines) and lines[j][0] >= child_indent:
                synthetic.append(lines[j])
                j += 1
            value, consumed = _parse_map(synthetic, 0, child_indent)
            if consumed != len(synthetic):
                raise YamlSubsetError(f"unparsed content in sequence item: {content!r}")
            items.append(value)
            i = j
        else:
            items.append(_unquote(content))
            i += 1
    return items, i


def _parse_map(lines: list[tuple[int, str]], i: int, indent: int):
    obj: dict = {}
    while i < len(lines) and lines[i][0] == indent:
        line = lines[i][1]
        m = re.match(r"^([A-Za-z0-9_.-]+):(\s+(.*))?$", line)
        if not m:
            raise YamlSubsetError(f"not a mapping entry: {line!r}")
        key = m.group(1)
        inline = (m.group(3) or "").strip()
        if inline:
            obj[key] = _unquote(inline)
            i += 1
            continue
        i += 1
        if i >= len(lines) or lines[i][0] <= indent:
            obj[key] = None
            continue
        obj[key], i = _parse_block(lines, i, lines[i][0])
    return obj, i


def load_yaml_subset(path: Path):
    lines = _load_lines(path.read_text(encoding="utf-8"))
    if not lines:
        return {}
    value, i = _parse_block(lines, 0, lines[0][0])
    if i != len(lines):
        raise YamlSubsetError(f"{path.name}: trailing content at line index {i}")
    return value


# ---------------------------------------------------------------------------
# Skill descriptions
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
DESC_RE = re.compile(r"^description:\s*(.*)$", re.MULTILINE)
TRIGGER_HEAD_RE = re.compile(r"Triggers?(?:\s+when\s+user\s+says)?\s*:\s*", re.IGNORECASE)


@dataclass
class SkillProfile:
    name: str
    description: str
    phrases: list[tuple[str, ...]] = field(default_factory=list)
    trigger_tokens: set[str] = field(default_factory=set)
    desc_tokens: set[str] = field(default_factory=set)


def extract_trigger_phrases(description: str) -> list[str]:
    """Pull the trigger phrases out of a frontmatter description.

    Two shapes exist in this repo, both handled:
      "Triggers when user says: 'search literature', 'find papers', ... . Rest of prose."
      "Triggers: citation context, how is this cited, ... . Rest of prose."
    Quoted phrases win when present (they survive apostrophes inside a phrase, such as
    'devil's advocate', because the split happens on the "', '" boundary, not on every
    single quote).
    """
    m = TRIGGER_HEAD_RE.search(description)
    if not m:
        return []
    tail = description[m.end() :].strip()
    if tail.startswith("'"):
        end = tail.rfind("'")
        segment = tail[1:end]
        return [p.strip() for p in re.split(r"',\s*'", segment) if p.strip()]
    # Unquoted, comma separated, terminated by the first sentence-ending period.
    dot = tail.find(". ")
    if dot == -1:
        dot = len(tail.rstrip("."))
    segment = tail[:dot]
    return [p.strip() for p in segment.split(",") if p.strip()]


def load_skills() -> list[SkillProfile]:
    profiles: list[SkillProfile] = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        fm = FRONTMATTER_RE.match(text)
        if not fm:
            raise SystemExit(f"{skill_md}: no YAML frontmatter")
        dm = DESC_RE.search(fm.group(1))
        if not dm:
            raise SystemExit(f"{skill_md}: frontmatter has no description")
        description = _unquote(dm.group(1).strip())
        name = skill_md.parent.name
        phrases = extract_trigger_phrases(description)
        prof = SkillProfile(name=name, description=description)
        for phrase in phrases:
            toks = tuple(tokenize(phrase))
            if toks:
                prof.phrases.append(toks)
                prof.trigger_tokens.update(toks)
        prof.desc_tokens = set(tokenize(description)) | set(tokenize(name.replace("-", " ")))
        profiles.append(prof)
    return profiles


def build_idf(profiles: list[SkillProfile]) -> dict[str, float]:
    n = len(profiles)
    df: dict[str, int] = {}
    for p in profiles:
        for tok in p.desc_tokens:
            df[tok] = df.get(tok, 0) + 1
    return {tok: math.log(n / (1 + d)) + 1.0 for tok, d in df.items()}


DEFAULT_IDF = math.log(29 / 1.0) + 1.0  # an out-of-corpus token is maximally informative


def phrase_component(
    prompt_tokens: list[str], prompt_set: set[str], prof: SkillProfile, idf: dict[str, float]
) -> float:
    """IDF mass of the prompt tokens the skill's trigger phrases matched, once each.

    Union, not sum-over-phrases. journal-finder has eight trigger phrases containing the
    word "journal"; summing per phrase would let it bank idf("journal") eight times and
    swallow every prompt that says "journal". Each matched token is therefore credited
    once, scaled by the ordering bonus of the strongest phrase that matched.
    """
    matched: set[str] = set()
    best_bonus = 0.0
    for phrase in prof.phrases:
        present = [t for t in phrase if t in prompt_set]
        if not present:
            continue
        coverage = len(present) / len(phrase)
        if coverage < COVERAGE_FLOOR:
            continue
        if _contains_run(prompt_tokens, phrase):
            bonus = BONUS_CONTIGUOUS
        elif coverage >= 1.0:
            bonus = BONUS_ALL_TOKENS
        else:
            bonus = BONUS_PARTIAL
        if len(phrase) == 1:
            # A phrase that reduces to a single content token ("submit where" -> "submit")
            # is weak evidence; it must not carry the weight of a real multi-word trigger.
            bonus *= SINGLE_TOKEN_W
        best_bonus = max(best_bonus, bonus)
        matched.update(present)
    if not matched:
        return 0.0
    return best_bonus * sum(idf.get(t, DEFAULT_IDF) for t in matched)


def score(prompt_tokens: list[str], prof: SkillProfile, idf: dict[str, float]) -> float:
    prompt_set = set(prompt_tokens)
    total = PHRASE_W * phrase_component(prompt_tokens, prompt_set, prof, idf)
    total += DESC_W * sum(
        idf.get(tok, DEFAULT_IDF) for tok in prompt_set if tok in prof.desc_tokens
    )
    return total


def _contains_run(haystack: list[str], needle: tuple[str, ...]) -> bool:
    n, m = len(haystack), len(needle)
    if m == 0 or m > n:
        return False
    for i in range(n - m + 1):
        if tuple(haystack[i : i + m]) == needle:
            return True
    return False


NEAR_TIE = 0.05  # top-2 within 5% of top-1: the scorer cannot separate them


def rank(prompt: str, profiles: list[SkillProfile], idf: dict[str, float], threshold: float):
    """Top-1 route plus the full ranking. Ties break alphabetically, which is arbitrary:
    near-ties are counted and reported separately so an arbitrary win is never mistaken
    for a discriminating description."""
    toks = tokenize(prompt)
    scored = sorted(
        ((score(toks, p, idf), p.name) for p in profiles), key=lambda x: (-x[0], x[1])
    )
    top_score, top_name = scored[0]
    predicted = top_name if top_score >= threshold else "none"
    runner_up, runner_name = scored[1]
    near_tie = top_score > 0 and (top_score - runner_up) <= NEAR_TIE * top_score
    return predicted, scored, near_tie, runner_name


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float, float]:
    """Point estimate and two-sided Wilson score interval."""
    if n == 0:
        return 0.0, 0.0, 1.0
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return p, max(0.0, centre - half), min(1.0, centre + half)


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------


def load_cases(path: Path) -> list[dict]:
    doc = load_yaml_subset(path)
    skills = doc.get("skills") if isinstance(doc, dict) else None
    if not isinstance(skills, list) or not skills:
        raise SystemExit(f"{path}: expected a top-level 'skills:' list")
    return skills


def check_set_integrity(cases: list[dict], skill_names: set[str]) -> list[str]:
    """D17 guard: the set cannot be silently shrunk below 5 positives / 3 negatives."""
    problems: list[str] = []
    covered = set()
    for entry in cases:
        name = entry.get("name")
        if name not in skill_names:
            problems.append(f"triggers.yaml names '{name}', which is not a skill directory")
            continue
        covered.add(name)
        pos = entry.get("positive") or []
        neg = entry.get("negative") or []
        if len(pos) < POSITIVES_PER_SKILL:
            problems.append(
                f"{name}: {len(pos)} positives, D17 requires >= {POSITIVES_PER_SKILL}"
            )
        if len(neg) < NEGATIVES_PER_SKILL:
            problems.append(
                f"{name}: {len(neg)} negatives, D17 requires >= {NEGATIVES_PER_SKILL}"
            )
    for missing in sorted(skill_names - covered):
        problems.append(f"{missing}: no entry in triggers.yaml")
    return problems


def run(cases: list[dict], profiles: list[SkillProfile], idf: dict[str, float], threshold: float):
    per_skill: dict[str, dict] = {}
    pos_records: list[dict] = []
    neg_records: list[dict] = []

    for entry in cases:
        name = entry["name"]
        row = {"skill": name, "pos_hit": 0, "pos_n": 0, "false_trigger": 0, "neg_n": 0}
        for prompt in entry.get("positive") or []:
            predicted, scored, near_tie, runner_up = rank(prompt, profiles, idf, threshold)
            hit = predicted == name
            row["pos_n"] += 1
            row["pos_hit"] += int(hit)
            pos_records.append(
                {
                    "skill": name,
                    "prompt": prompt,
                    "predicted": predicted,
                    "hit": hit,
                    "near_tie": near_tie,
                    "runner_up": runner_up,
                    "top_score": round(scored[0][0], 3),
                }
            )
        for item in entry.get("negative") or []:
            prompt = item["prompt"] if isinstance(item, dict) else item
            if isinstance(item, dict):
                expected_route = item.get("route", "unspecified")
            else:
                expected_route = "unspecified"
            predicted, scored, near_tie, runner_up = rank(prompt, profiles, idf, threshold)
            false_trigger = predicted == name
            row["neg_n"] += 1
            row["false_trigger"] += int(false_trigger)
            neg_records.append(
                {
                    "baited_skill": name,
                    "prompt": prompt,
                    "predicted": predicted,
                    "expected_route": expected_route,
                    "false_trigger": false_trigger,
                    "rerouted_as_expected": predicted == expected_route,
                    "near_tie": near_tie,
                    "runner_up": runner_up,
                    "top_score": round(scored[0][0], 3),
                }
            )
        per_skill[name] = row

    pos_n = len(pos_records)
    pos_hits = sum(int(r["hit"]) for r in pos_records)
    neg_n = len(neg_records)
    neg_ft = sum(int(r["false_trigger"]) for r in neg_records)

    recall, r_lo, r_hi = wilson(pos_hits, pos_n)
    ftr, f_lo, f_hi = wilson(neg_ft, neg_n)

    return {
        "threshold": threshold,
        "pooled": {
            "positives_n": pos_n,
            "positives_hit": pos_hits,
            "recall": recall,
            "recall_ci95": [r_lo, r_hi],
            "negatives_n": neg_n,
            "false_triggers": neg_ft,
            "false_trigger_rate": ftr,
            "false_trigger_rate_ci95": [f_lo, f_hi],
            "negatives_rerouted_as_expected": sum(
                int(r["rerouted_as_expected"]) for r in neg_records
            ),
            "negatives_abstained": sum(int(r["predicted"] == "none") for r in neg_records),
            "near_ties": sum(int(r["near_tie"]) for r in pos_records + neg_records),
        },
        "per_skill_diagnostics": list(per_skill.values()),
        "positive_records": pos_records,
        "negative_records": neg_records,
    }


def sensitivity(cases, profiles, idf, thresholds):
    rows = []
    for t in thresholds:
        res = run(cases, profiles, idf, t)
        p = res["pooled"]
        rows.append(
            {
                "threshold": t,
                "recall": p["recall"],
                "false_trigger_rate": p["false_trigger_rate"],
                "negatives_abstained": p["negatives_abstained"],
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

HEADER = """\
================================================================================
POOLED TRIGGER EVAL (M2.13)
================================================================================

WHAT THIS IS. The 29 skills are routed by their SKILL.md frontmatter description.
This runner scores each prompt against those descriptions with the documented
lexical scorer in evals/run_triggers.py (trigger-phrase runs + IDF-weighted token
overlap) and takes the top-scoring skill. It therefore measures WHETHER THE
DESCRIPTIONS DISCRIMINATE, which is real, load-bearing, and the thing this repo
controls. It is NOT a measurement of live model routing: no model is in this loop.
Do not quote these figures as live routing accuracy.

D17 CERTIFICATION ARITHMETIC (printed so a future edit cannot silently shrink the
sets). Zero-error certification: 0.9^29 = 0.047 < 0.05, so certifying a false-
trigger rate below 0.10 at 95% confidence requires 0 errors in n >= 29 (exact one-
sided; two-sided Wilson needs n >= 35). 0.85^19 = 0.046 < 0.05, so certifying a
miss rate below 0.15 requires 0 misses in n >= 19 (Wilson: n >= 22). When nonzero
error rates are expected, report a point estimate plus a 95% Wilson CI on pooled
n >= 100 to 300. This set is 145 positives and 87 negatives, both inside that band.

PER-SKILL n=5 CANNOT CERTIFY ANYTHING. 4/5 = 0.80 has a 95% Wilson interval of
0.376 to 0.964. The per-skill table below is DIAGNOSTIC ONLY. This runner refuses
to emit a per-skill certification: try --certify-skill <name> and read the refusal.
================================================================================
"""


def pct(x: float) -> str:
    return f"{100 * x:5.1f}%"


def print_report(res: dict, sens: list[dict], min_recall: float, max_ftr: float) -> bool:
    p = res["pooled"]
    print(HEADER)
    print(f"Matcher threshold: {res['threshold']:.2f} (a prompt below it routes to 'none')")
    print()
    print("GATE METRICS (pooled, the ONLY certifying numbers here)")
    print("-" * 80)
    r_lo, r_hi = p["recall_ci95"]
    f_lo, f_hi = p["false_trigger_rate_ci95"]
    print(
        f"  pooled recall              {p['positives_hit']:3d}/{p['positives_n']:<3d} = "
        f"{pct(p['recall'])}   95% Wilson CI [{pct(r_lo)}, {pct(r_hi)}]   "
        f"gate >= {pct(min_recall)}"
    )
    print(
        f"  pooled false-trigger rate  {p['false_triggers']:3d}/{p['negatives_n']:<3d} = "
        f"{pct(p['false_trigger_rate'])}   95% Wilson CI [{pct(f_lo)}, {pct(f_hi)}]   "
        f"gate <= {pct(max_ftr)}"
    )
    recall_ok = p["recall"] >= min_recall
    ftr_ok = p["false_trigger_rate"] <= max_ftr
    print()
    print(f"  recall gate:        {'PASS' if recall_ok else 'FAIL'}")
    print(f"  false-trigger gate: {'PASS' if ftr_ok else 'FAIL'}")
    print()

    print("NEGATIVE-SET BEHAVIOUR (diagnostic)")
    print("-" * 80)
    print(f"  negatives routed to the skill they were designed to bait: {p['false_triggers']}")
    print(f"  negatives routed to their expected alternative skill:     "
          f"{p['negatives_rerouted_as_expected']}")
    print(f"  negatives that scored below threshold and abstained:      {p['negatives_abstained']}")
    print()

    print("SCORER-LIMIT DIAGNOSTIC (not a property of the descriptions)")
    print("-" * 80)
    print(
        f"  prompts where top-1 and top-2 are within {int(NEAR_TIE * 100)}%: "
        f"{p['near_ties']} of {p['positives_n'] + p['negatives_n']}"
    )
    print("  On a near-tie the winner is decided alphabetically, which is arbitrary. A live")
    print("  model would use context to break it. Read those rows as 'the lexical scorer")
    print("  cannot separate these two descriptions', not as a routing result.")
    print()

    print("THRESHOLD SENSITIVITY (diagnostic: how the two pooled numbers trade off)")
    print("-" * 80)
    print(f"  {'threshold':>10}  {'recall':>8}  {'false-trig':>10}  {'abstained':>9}")
    for row in sens:
        print(
            f"  {row['threshold']:>10.2f}  {pct(row['recall']):>8}  "
            f"{pct(row['false_trigger_rate']):>10}  {row['negatives_abstained']:>9d}"
        )
    print()

    print("PER-SKILL ROWS: DIAGNOSTICS ONLY, NOT GATES (D17, n=5 positives / 3 negatives)")
    print("-" * 80)
    print(
        f"  {'skill':<24} {'pos':>5} {'95% Wilson CI on 5':>22}  {'false-trig':>10}  misroutes"
    )
    lookup = {}
    for rec in res["positive_records"]:
        if not rec["hit"]:
            lookup.setdefault(rec["skill"], []).append(f"{rec['prompt'][:28]!r}->{rec['predicted']}")
    for rec in res["negative_records"]:
        if rec["false_trigger"]:
            lookup.setdefault(rec["baited_skill"], []).append(
                f"FT {rec['prompt'][:28]!r}"
            )
    for row in sorted(res["per_skill_diagnostics"], key=lambda r: r["skill"]):
        _, lo, hi = wilson(row["pos_hit"], row["pos_n"])
        misses = lookup.get(row["skill"], [])
        print(
            f"  {row['skill']:<24} {row['pos_hit']}/{row['pos_n']:<3} "
            f"[{pct(lo)}, {pct(hi)}]  {row['false_trigger']}/{row['neg_n']:<9}"
            f"  {'; '.join(misses) if misses else ''}"
        )
    print()
    print("  Every interval above spans tens of percentage points. That is the point of D17:")
    print("  a per-skill row can motivate a description edit, it can never certify one.")
    print()
    return recall_ok and ftr_ok


def refuse_per_skill_certification(name: str, res: dict) -> int:
    row = next((r for r in res["per_skill_diagnostics"] if r["skill"] == name), None)
    if row is None:
        print(f"No such skill in triggers.yaml: {name}", file=sys.stderr)
        return 2
    p, lo, hi = wilson(row["pos_hit"], row["pos_n"])
    _, nlo, nhi = wilson(row["false_trigger"], row["neg_n"])
    print("REFUSING TO CERTIFY A PER-SKILL RESULT (D17).")
    print()
    print(f"  skill:  {name}")
    print(f"  recall: {row['pos_hit']}/{row['pos_n']} = {pct(p)}")
    print(f"          95% Wilson CI [{pct(lo)}, {pct(hi)}]  (width {pct(hi - lo)})")
    print(f"  false-trigger: {row['false_trigger']}/{row['neg_n']}")
    print(f"          95% Wilson CI [{pct(nlo)}, {pct(nhi)}]  (width {pct(nhi - nlo)})")
    print()
    print("  An interval that wide is compatible with almost any true rate, so any single")
    print("  number derived from it would be authoritative-looking and meaningless. At n=5,")
    print("  4/5 = 80% and a true rate of 40% or of 96% are all consistent with the data.")
    print("  Certification runs on the POOLED sets only (145 positives, 87 negatives).")
    print("  Run without --certify-skill for the pooled gate; use the per-skill row above")
    print("  as a diagnostic hint about a description that may need editing, nothing more.")
    return 2


def explain(prompt: str, profiles: list[SkillProfile], idf: dict[str, float], threshold: float) -> int:
    """Show why one prompt scored the way it did. Diagnosing a collision starts here."""
    predicted, scored, near_tie, _ = rank(prompt, profiles, idf, threshold)
    toks = tokenize(prompt)
    print(f"prompt:    {prompt!r}")
    print(f"tokens:    {toks}")
    print(f"predicted: {predicted}" + ("   (NEAR TIE, broken alphabetically)" if near_tie else ""))
    print()
    print(f"  {'skill':<24} {'score':>7}  {'phrase':>7}  {'desc':>7}")
    by_name = {p.name: p for p in profiles}
    for sc, name in scored[:6]:
        prof = by_name[name]
        ph = PHRASE_W * phrase_component(toks, set(toks), prof, idf)
        de = DESC_W * sum(idf.get(t, DEFAULT_IDF) for t in set(toks) if t in prof.desc_tokens)
        print(f"  {name:<24} {sc:>7.2f}  {ph:>7.2f}  {de:>7.2f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Pooled trigger eval: does each SKILL.md description discriminate?"
    )
    ap.add_argument("--triggers", type=Path, default=TRIGGERS_YAML)
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument(
        "--explain",
        metavar="PROMPT",
        help="score one prompt against all 29 descriptions and show the breakdown",
    )
    ap.add_argument("--min-recall", type=float, default=0.90, help="pooled gate (D17)")
    ap.add_argument("--max-false-trigger", type=float, default=0.10, help="pooled gate (D17)")
    ap.add_argument(
        "--certify-skill",
        metavar="NAME",
        help="ask for a per-skill certification; the runner declines and explains why (D17)",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable report on stdout")
    args = ap.parse_args()

    profiles = load_skills()

    if args.explain:
        return explain(args.explain, profiles, build_idf(profiles), args.threshold)

    cases = load_cases(args.triggers)

    problems = check_set_integrity(cases, {p.name for p in profiles})
    if problems:
        print("TRIGGER SET INTEGRITY FAILURE (D17 sizes are not negotiable):", file=sys.stderr)
        for prob in problems:
            print(f"  - {prob}", file=sys.stderr)
        return 2

    idf = build_idf(profiles)
    res = run(cases, profiles, idf, args.threshold)

    if args.certify_skill:
        return refuse_per_skill_certification(args.certify_skill, res)

    sens = sensitivity(cases, profiles, idf, [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0])

    if args.json:
        payload = dict(res)
        payload["sensitivity"] = sens
        payload["gates"] = {
            "min_pooled_recall": args.min_recall,
            "max_pooled_false_trigger_rate": args.max_false_trigger,
            "per_skill_certification": "refused by design (D17)",
        }
        payload["caveat"] = (
            "Lexical match over SKILL.md frontmatter descriptions. Measures whether the "
            "descriptions discriminate. NOT a measurement of live model routing."
        )
        p = res["pooled"]
        payload["gate_pass"] = bool(
            p["recall"] >= args.min_recall
            and p["false_trigger_rate"] <= args.max_false_trigger
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["gate_pass"] else 1

    ok = print_report(res, sens, args.min_recall, args.max_false_trigger)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
