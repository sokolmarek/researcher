#!/usr/bin/env python
"""The M5.4 export gate: round-trip a fixture set through every emitter and MEASURE the losses.

CSL-JSON is canonical (D4). BibTeX, RIS, and JATS ``<ref-list>`` are emitters. This runner takes
the hard-case fixtures in ``evals/fixtures/roundtrip/cases.json`` and, for each format, runs the
``CSL -> emitter -> re-import -> CSL`` round-trip, then reports two things per format:

* **Losslessness for carried fields.** Every field the format's :class:`~researcher_core.export.
  FormatLoss` entry marks as ``carried`` must survive the round-trip byte for byte. A carried
  field that changed is a SILENT LOSS and fails the gate: the whole point is that a field the
  format cannot carry is written down, never dropped without record.
* **The loss table, verified against reality.** Each documented ``lost`` field is checked to have
  actually dropped on at least one fixture (or the maximal probe), so the table is neither padded
  with losses that never happen nor silent about losses that do.

Unlike the axis runners this gate is PURELY OFFLINE and needs no snapshots: it never touches the
network and never resolves a DOI (the sanctioned ``expect-unresolvable`` fake, D8, is carried as
data only). Two consecutive runs produce byte-identical output: nothing here reads a clock,
orders by completion, or iterates a set.

Usage::

    uv run --project core python evals/run_roundtrip.py            # human-readable report
    uv run --project core python evals/run_roundtrip.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
FIXTURE_DIR = EVALS_DIR / "fixtures" / "roundtrip"
CASES_FILE = FIXTURE_DIR / "cases.json"

# The kernel lives in core/. `uv run --project core` already has it importable; adding it to
# sys.path lets a plain `python evals/run_roundtrip.py` work from a bare checkout too.
sys.path.insert(0, str(REPO_ROOT / "core"))

from researcher_core import __version__ as CORE_VERSION  # noqa: E402
from researcher_core.export import (  # noqa: E402
    COMPARABLE_FIELDS,
    FORMATS,
    LOSS_TABLE,
    field_diff,
    record_fields,
    roundtrip,
)
from researcher_core.model import CSLRecord  # noqa: E402


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {})


@dataclass
class CaseOutcome:
    """One fixture round-tripped through one format."""

    case_id: str
    fmt: str
    silent_losses: list[str] = field(default_factory=list)
    documented_losses: list[str] = field(default_factory=list)
    carried_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.silent_losses


@dataclass
class FormatReport:
    fmt: str
    outcomes: list[CaseOutcome] = field(default_factory=list)
    losses_seen: set[str] = field(default_factory=set)

    @property
    def failures(self) -> list[CaseOutcome]:
        return [outcome for outcome in self.outcomes if not outcome.ok]

    @property
    def carried_checked(self) -> int:
        return sum(outcome.carried_checked for outcome in self.outcomes)


@dataclass
class RoundtripResult:
    reports: dict[str, FormatReport] = field(default_factory=dict)
    n_cases: int = 0
    unverified_table_entries: dict[str, list[str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        no_silent = all(not report.failures for report in self.reports.values())
        table_real = not any(self.unverified_table_entries.values())
        return no_silent and table_real


def load_cases() -> list[dict[str, Any]]:
    data = json.loads(CASES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{CASES_FILE} must be a JSON array of case objects")
    return data


def score_case(case: dict[str, Any], fmt: str) -> CaseOutcome:
    """Round-trip one fixture through one format and score it against the loss table."""
    record = CSLRecord.from_csl_json(case["record"])
    before = record_fields(record)
    after = record_fields(roundtrip(fmt, [record])[0])
    changed = field_diff(before, after)

    profile = LOSS_TABLE[fmt]
    extra = set(case.get("expected_extra_loss", {}).get(fmt, []))
    declared = set(profile.lost) | extra

    carried_checked = sum(
        1 for name in profile.carried if name not in extra and not _is_empty(before.get(name))
    )
    return CaseOutcome(
        case_id=str(case["id"]),
        fmt=fmt,
        silent_losses=sorted(changed - declared),
        documented_losses=sorted(changed & declared),
        carried_checked=carried_checked,
    )


def maximal_probe() -> CSLRecord:
    """A record that populates every comparable field, so every declared loss is exercised.

    It carries both an ISSN and an ISBN (RIS can hold only one), a version and a report number
    (RIS and JATS lack fields for them), an abstract, keywords and a language (JATS lacks all
    three), a non-default id (JATS regenerates it), and a day-of-month (BibTeX drops it). The
    title deliberately avoids literal braces so the probe measures the STRUCTURAL losses, not the
    BibTeX brace-grouping behaviour that the ``braces-and-markup`` fixture covers.
    """
    return CSLRecord.from_csl_json(
        {
            "id": "probe-key-001",
            "type": "article-journal",
            "title": "Möbius Bänder & <Deep> Learning: a Review",
            "author": [
                {"family": "Ribeiro", "given": "Antônio H.", "suffix": "Jr."},
                {"literal": "World Health Organization"},
            ],
            "editor": [{"family": "Erdős", "given": "Paul"}],
            "issued": {"date-parts": [[2021, 5, 17]]},
            "container-title": "Journal of Tésting & Review",
            "publisher": "Académie Press",
            "volume": "12",
            "issue": "4",
            "page": "1541-1554",
            "number": "TR-99",
            "version": "2.1.0",
            "abstract": "An abstract with <tags> & ampersands.",
            "DOI": "10.1234/probe.2021.001",
            "URL": "https://example.org/a?b=1&c=2",
            "ISSN": ["1234-5678", "8765-4321"],
            "ISBN": "978-3-16-148410-0",
            "language": "en",
            "note": "A note; with punctuation.",
            "keyword": ["alpha", "beta"],
        }
    )


def run(cases: list[dict[str, Any]]) -> RoundtripResult:
    result = RoundtripResult(n_cases=len(cases))
    probe = maximal_probe()
    probe_before = record_fields(probe)

    for fmt in FORMATS:
        report = FormatReport(fmt=fmt)
        for case in cases:
            outcome = score_case(case, fmt)
            report.outcomes.append(outcome)
            report.losses_seen.update(outcome.documented_losses)

        # The probe exercises every field at once, so every structural loss shows here.
        probe_after = record_fields(roundtrip(fmt, [probe])[0])
        probe_changed = field_diff(probe_before, probe_after)
        report.losses_seen.update(probe_changed & set(LOSS_TABLE[fmt].lost))
        probe_silent = sorted(probe_changed - set(LOSS_TABLE[fmt].lost))
        report.outcomes.append(
            CaseOutcome(
                case_id="_maximal_probe",
                fmt=fmt,
                silent_losses=probe_silent,
                documented_losses=sorted(probe_changed & set(LOSS_TABLE[fmt].lost)),
                carried_checked=sum(
                    1 for name in LOSS_TABLE[fmt].carried if not _is_empty(probe_before.get(name))
                ),
            )
        )

        result.reports[fmt] = report
        declared = set(LOSS_TABLE[fmt].lost)
        result.unverified_table_entries[fmt] = sorted(declared - report.losses_seen)

    return result


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(result: RoundtripResult) -> str:
    out: list[str] = [
        "=" * 78,
        "RESEARCHER EVIDENCE KERNEL: EXPORT ROUND-TRIP GATE (M5.4)",
        "=" * 78,
        "",
        f"core version    {CORE_VERSION}",
        "mode            offline; no network, no snapshots, no DOI resolution",
        f"fixtures        {result.n_cases} hard cases + 1 maximal probe, per format",
        f"formats         {', '.join(FORMATS)}",
        "",
        "  CSL-JSON is canonical (D4). A round-trip is CSL -> emitter -> re-import -> CSL. A field",
        "  the format CAN carry must survive byte for byte; a field it cannot is listed in the",
        "  loss table below, never dropped silently. A silent loss (a carried field that changed)",
        "  fails the gate.",
        "",
        "-" * 78,
        "PER-FORMAT LOSSLESSNESS",
        "-" * 78,
    ]
    for fmt in FORMATS:
        report = result.reports[fmt]
        failures = report.failures
        status = "LOSSLESS" if not failures else f"!! {len(failures)} SILENT LOSS !!"
        out.append("")
        out.append(f"  {fmt:<9}  {status}")
        out.append(
            f"    carried-field checks {report.carried_checked:>4}   "
            f"cases {len(report.outcomes)} (incl. probe)"
        )
        losses = LOSS_TABLE[fmt].lost
        out.append(
            "    documented losses    "
            + (", ".join(losses) if losses else "none (identity round-trip)")
        )
        seen = sorted(report.losses_seen)
        out.append("    losses observed      " + (", ".join(seen) if seen else "none"))
        for outcome in failures:
            out.append(
                f"      SILENT LOSS in {outcome.case_id}: {', '.join(outcome.silent_losses)}"
            )
        unverified = result.unverified_table_entries.get(fmt, [])
        if unverified:
            out.append(
                "      !! table lists losses never observed on any fixture: "
                + ", ".join(unverified)
            )

    out.extend(
        [
            "",
            "-" * 78,
            "PER-FORMAT LOSS TABLE (published in evals/fixtures/roundtrip/README.md)",
            "-" * 78,
        ]
    )
    for fmt in FORMATS:
        profile = LOSS_TABLE[fmt]
        out.append("")
        out.append(f"  {fmt}")
        out.append(
            "    cannot carry: "
            + (", ".join(profile.lost) if profile.lost else "nothing (canonical)")
        )
        for note in profile.notes:
            out.append(f"      - {note}")

    out.extend(
        [
            "",
            "=" * 78,
            "RESULT: " + ("all formats lossless for their carried fields, loss table verified"
            if result.ok
            else "GATE FAILED: a silent loss or an unverified table entry above"),
            "=" * 78,
            "",
        ]
    )
    return "\n".join(out)


def to_json(result: RoundtripResult) -> dict[str, Any]:
    return {
        "core_version": CORE_VERSION,
        "comparable_fields": list(COMPARABLE_FIELDS),
        "n_cases": result.n_cases,
        "ok": result.ok,
        "formats": {
            fmt: {
                "lossless": not result.reports[fmt].failures,
                "carried_field_checks": result.reports[fmt].carried_checked,
                "documented_lost": list(LOSS_TABLE[fmt].lost),
                "losses_observed": sorted(result.reports[fmt].losses_seen),
                "unverified_table_entries": result.unverified_table_entries.get(fmt, []),
                "notes": list(LOSS_TABLE[fmt].notes),
                "silent_losses": {
                    outcome.case_id: outcome.silent_losses
                    for outcome in result.reports[fmt].failures
                },
            }
            for fmt in FORMATS
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_roundtrip.py",
        description="Round-trip the export fixtures through every emitter and report the losses.",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument(
        "--out", type=Path, help="write the report to this file as well as to stdout"
    )
    args = parser.parse_args(argv)

    cases = load_cases()
    result = run(cases)

    if args.json:
        text = json.dumps(to_json(result), indent=2, sort_keys=True, ensure_ascii=False)
    else:
        text = render(result)

    sys.stdout.write(text + "\n")
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
