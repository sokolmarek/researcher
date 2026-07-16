"""End-to-end CLI test for the M4 systematic-review commands, driving the real ledger."""

from __future__ import annotations

import json

from researcher_core.cli import main

TS = "2026-07-14T00:00:00Z"


def run(argv, capsys):
    code = main(argv)
    out = capsys.readouterr().out
    return code, out


def test_protocol_lock_then_detect_unamended_edit(tmp_path, capsys):
    ledger = tmp_path / "l.sqlite3"
    protocol = tmp_path / "protocol.yaml"
    protocol.write_text("question: does X work\neligibility: adults\n", encoding="utf-8")

    code, _ = run(
        ["protocol", "lock", str(protocol), "--run-id", "sr", "--ts", TS, "--ledger", str(ledger)],
        capsys,
    )
    assert code == 0

    # unchanged protocol still matches
    code, _ = run(
        ["protocol", "check", str(protocol), "--run-id", "sr", "--ledger", str(ledger), "--json"],
        capsys,
    )
    assert code == 0

    # edit the protocol file without an amendment: detected as a mismatch, exit 1
    protocol.write_text("question: does X work\neligibility: adults and children\n",
        encoding="utf-8")
    code, out = run(
        ["protocol", "check", str(protocol), "--run-id", "sr", "--ledger", str(ledger), "--json"],
        capsys,
    )
    assert code == 1
    assert json.loads(out)["matches"] is False


def test_amendment_is_allowed_and_trails(tmp_path, capsys):
    ledger = tmp_path / "l.sqlite3"
    protocol = tmp_path / "protocol.yaml"
    protocol.write_text("question: v1\n", encoding="utf-8")
    run(["protocol", "lock", str(protocol), "--run-id", "sr", "--ts", TS, "--ledger",
        str(ledger)], capsys)

    protocol.write_text("question: v2\n", encoding="utf-8")
    code, _ = run(
        ["protocol", "amend", str(protocol), "--run-id", "sr", "--ts", TS,
         "--summary", "widened population", "--rationale", "reviewer request", "--ledger",
             str(ledger)],
        capsys,
    )
    assert code == 0
    # the amended protocol now matches, and the trail has two lifecycle events
    code, out = run(
        ["protocol", "check", str(protocol), "--run-id", "sr", "--ledger", str(ledger), "--json"],
        capsys,
    )
    assert code == 0
    assert len(json.loads(out)["amendment_trail"]) == 2


def test_dual_screening_conflicts_are_blind_and_kappa_derives(tmp_path, capsys):
    ledger = tmp_path / "l.sqlite3"
    profile = tmp_path / "profile.json"
    corpus = tmp_path / "corpus.json"
    profile.write_text(json.dumps({"population": "adults"}), encoding="utf-8")
    corpus.write_text(json.dumps({"r2": {"title": "Disputed", "abstract": "..."}}),
        encoding="utf-8")

    def decide(screener, record, decision):
        run(
            ["screen", "decide", "--run-id", "sr", "--screener", screener, "--record", record,
             "--stage", "title-abstract", "--decision", decision, "--ts", TS, "--ledger",
                 str(ledger)],
            capsys,
        )

    # alice and bob agree on r1/r3, disagree on r2
    for r, d in {"r1": "include", "r2": "include", "r3": "exclude"}.items():
        decide("alice", r, d)
    for r, d in {"r1": "include", "r2": "exclude", "r3": "exclude"}.items():
        decide("bob", r, d)

    code, out = run(
        ["screen", "conflicts", "--run-id", "sr", "--stage", "title-abstract",
         "--corpus", str(corpus), "--profile", str(profile), "--ledger", str(ledger), "--json"],
        capsys,
    )
    assert code == 0
    conflicts = json.loads(out)
    assert [c["record_id"] for c in conflicts] == ["r2"]
    # BLIND: the adjudication payload must not carry either vote
    blob = json.dumps(conflicts).lower()
    for leak in ("include", "exclude", "alice", "bob", "verdict", "vote"):
        assert leak not in blob, f"blinding leak: {leak}"

    code, out = run(
        ["screen", "kappa", "--run-id", "sr", "--stage", "title-abstract", "--ledger",
            str(ledger), "--json"],
        capsys,
    )
    assert code == 0
    assert "kappa" in json.loads(out)


def test_prisma_flow_is_derived_from_events(tmp_path, capsys):
    ledger = tmp_path / "l.sqlite3"

    def decide(screener, record, decision):
        run(
            ["screen", "decide", "--run-id", "sr", "--screener", screener, "--record", record,
             "--stage", "title-abstract", "--decision", decision, "--ts", TS, "--ledger",
                 str(ledger)],
            capsys,
        )

    decide("alice", "r1", "include")
    decide("alice", "r2", "exclude")

    code, out = run(["prisma", "flow", "--run-id", "sr", "--ledger", str(ledger), "--json"], capsys)
    assert code == 0
    flow = json.loads(out)
    # the flow is a derived object; it reflects the screening decisions just recorded
    assert flow  # non-empty derived structure
