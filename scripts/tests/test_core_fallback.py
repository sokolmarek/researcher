"""The plugin must never hard-fail without researcher-core (D3).

Every script that prefers core has to degrade to its M1 stdlib logic when core is not
there, is broken, or is turned off, and the DECISIONS it makes (what blocks, what exits
non-zero) must not change with it. These tests run each script twice, once with core and
once without, and compare.

"Without core" is simulated the honest way: RESEARCHER_CORE_PROJECT points at a directory
that does not exist, so the resolver finds no core to run. "With core" is simulated with a
fake core (fixtures/fake_core.py) wired in through RESEARCHER_CORE_CMD, which emits a
report in the shape of core/schemas/verification-report.schema.json. The fake is what
keeps these tests offline and deterministic: the real core would call OpenAlex and
Crossref, and a commit guard's test suite may not depend on the internet.

The boundary these tests pin down, and the one thing easy to get wrong: a RETRACTED
citation is REPORTED by the commit guard, NEVER BLOCKED by it. The hard block on
retractions arrives with the M3 compile gate. Same for refusal-grade identity findings.
The only thing this hook blocks on, with or without core, is a dangling citation key.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
GUARD = SCRIPTS / "citation-check-hook.py"
VALIDATOR = SCRIPTS / "bib-validator.py"
DRAFT_HOOK = SCRIPTS / "draft-integrity-hook.py"
FAKE_CORE = Path(__file__).resolve().parent / "fixtures" / "fake_core.py"
REPO_ROOT = SCRIPTS.parent

MAIN_TEX = """\\documentclass{article}
\\begin{document}
\\input{introduction}
\\bibliography{references/library}
\\end{document}
"""


# ---------------------------------------------------------------------------
# Environments: with core, without core, and with a core that is broken
# ---------------------------------------------------------------------------

def base_env(tmp_path):
    env = dict(os.environ)
    env.pop("RESEARCHER_CORE", None)
    env.pop("RESEARCHER_CORE_CMD", None)
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    # Never let a developer's real core (or a real network call) leak into these tests.
    env["RESEARCHER_CORE_PROJECT"] = str(tmp_path / "no-such-core")
    env["RESEARCHER_CORE_TIMEOUT"] = "60"
    return env


def env_without_core(tmp_path):
    """The plugin-only user: no uv, no core. The resolver finds nothing to run."""
    return base_env(tmp_path)


def env_with_core(tmp_path, marker=None):
    env = base_env(tmp_path)
    env["RESEARCHER_CORE_CMD"] = json.dumps([sys.executable, str(FAKE_CORE)])
    if marker is not None:
        env["FAKE_CORE_MARKER"] = str(marker)
    return env


def env_with_broken_core(tmp_path):
    """Core is installed but cannot answer: it crashes, or it is too old for verify-bib."""
    env = base_env(tmp_path)
    env["RESEARCHER_CORE_CMD"] = json.dumps(
        [sys.executable, "-c", "import sys; sys.stdout.write('not json'); sys.exit(2)"]
    )
    return env


# ---------------------------------------------------------------------------
# Repo helpers (same shape as test_citation_check_hook.py)
# ---------------------------------------------------------------------------

def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, timeout=30)


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "manuscript" / "references").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t.t")
    git(repo, "config", "user.name", "t")
    return repo


def write(repo, rel, text):
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run_guard(repo, env, command="git commit -m test"):
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(repo),
    })
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload, capture_output=True, text=True, encoding="utf-8",
        timeout=120, env=env,
    )


def run_validator(bib, env, *flags):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(bib), *flags],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
    )


def run_draft_hook(tex_path, env):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(tex_path)}})
    return subprocess.run(
        [sys.executable, str(DRAFT_HOOK)],
        input=payload, capture_output=True, text=True, encoding="utf-8",
        timeout=60, env=env,
    )


# The bib the fake core knows how to judge: one clean entry, one retracted entry, one
# invented entry, one entry whose DOI resolves to a different paper.
BIB = (
    "@article{good2020, title={A Fine Paper}, author={Doe, Jane},\n"
    "  journal={Journal of Tests}, year={2020}, doi={10.1234/fine}}\n"
    "@article{retracted2019, title={A Withdrawn Paper}, author={Roe, Rick},\n"
    "  journal={Journal of Tests}, year={2019}, doi={10.1234/retracted-work}}\n"
)
BIB_WITH_GHOST = BIB + (
    "@article{ghost2024, title={A Paper Nobody Wrote}, author={Nemo, Nemo},\n"
    "  journal={Journal of Tests}, year={2024}, doi={10.9999/ghost}}\n"
)
BIB_WITH_WRONGDOI = BIB + (
    "@article{wrongdoi2021, title={Right Paper Wrong Identifier}, author={Poe, Pat},\n"
    "  journal={Journal of Tests}, year={2021}, doi={10.1234/wrongdoi}}\n"
)


# ---------------------------------------------------------------------------
# The commit guard: identical decisions with and without core
# ---------------------------------------------------------------------------

def test_dangling_cite_blocks_identically_with_and_without_core(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex",
          "Cited \\cite{good2020} and missing \\cite{missing2024}.")
    write(repo, "manuscript/references/library.bib", BIB)
    git(repo, "add", "-A")

    without = run_guard(repo, env_without_core(tmp_path))
    with_core = run_guard(repo, env_with_core(tmp_path))

    assert without.returncode == 2, without.stderr
    assert with_core.returncode == 2, with_core.stderr
    for result in (without, with_core):
        assert "missing2024" in result.stderr
        assert "commit blocked" in result.stderr


def test_clean_commit_passes_identically_with_and_without_core(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Cited \\cite{good2020}.")
    write(repo, "manuscript/references/library.bib", BIB)
    git(repo, "add", "-A")

    assert run_guard(repo, env_without_core(tmp_path)).returncode == 0
    assert run_guard(repo, env_with_core(tmp_path)).returncode == 0


def test_retraction_is_reported_by_core_and_never_blocks(tmp_path):
    """Axis (b) reaches the commit guard, and it stays advisory.

    A retracted citation is real information at commit time, so it is printed. It is not
    a dangling key, so the commit still succeeds, and the report says so in as many words.
    The hard gate is M3's compile gate, not this hook.
    """
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex",
          "Solid \\cite{good2020}, and pulled \\cite{retracted2019}.")
    write(repo, "manuscript/references/library.bib", BIB)
    git(repo, "add", "-A")

    without = run_guard(repo, env_without_core(tmp_path))
    with_core = run_guard(repo, env_with_core(tmp_path))

    # The decision is identical: the commit is allowed either way.
    assert without.returncode == 0, without.stderr
    assert with_core.returncode == 0, with_core.stderr

    # Only the core run knows about the retraction, and it says it did not block.
    assert "retracted" not in without.stderr.lower()
    assert "retracted" in with_core.stderr.lower()
    assert "retracted2019" in with_core.stderr
    assert "REPORTED, NOT BLOCKED" in with_core.stderr
    assert "blocked." not in with_core.stderr  # no wording that implies a block happened


def test_refusal_grade_findings_are_reported_and_do_not_block(tmp_path):
    """unresolvable and mismatch are refusal-grade, but this hook is not the refuser.

    They surface in the report; the exit code stays 0 because no citation key dangles.
    """
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex",
          "Invented \\cite{ghost2024} and mis-identified \\cite{wrongdoi2021}.")
    write(repo, "manuscript/references/library.bib", BIB_WITH_GHOST + BIB_WITH_WRONGDOI)
    git(repo, "add", "-A")

    result = run_guard(repo, env_with_core(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "unresolvable" in result.stderr
    assert "ghost2024" in result.stderr
    assert "mismatch" in result.stderr
    assert "wrongdoi2021" in result.stderr
    assert "REPORTED, NOT BLOCKED" in result.stderr

    # Without core, none of that is known, and the commit still passes.
    without = run_guard(repo, env_without_core(tmp_path))
    assert without.returncode == 0
    assert without.stderr == ""


def test_broken_core_falls_back_and_still_blocks(tmp_path):
    """A core that crashes or prints garbage must not disarm the guard, nor break it."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Missing \\cite{missing2024}.")
    write(repo, "manuscript/references/library.bib", BIB)
    git(repo, "add", "-A")

    broken = run_guard(repo, env_with_broken_core(tmp_path))
    without = run_guard(repo, env_without_core(tmp_path))

    assert broken.returncode == without.returncode == 2
    assert "missing2024" in broken.stderr
    assert "did not run" in broken.stderr  # the miss is stated, not hidden


def test_core_is_not_consulted_when_no_entry_carries_a_doi(tmp_path):
    """No DOI, nothing for an index to resolve: the guard must not pay for a core call."""
    marker = tmp_path / "core-was-called"
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Cited \\cite{nodoi2020}.")
    write(repo, "manuscript/references/library.bib",
          "@article{nodoi2020, title={No Identifier}, year={2020}}")
    git(repo, "add", "-A")

    result = run_guard(repo, env_with_core(tmp_path, marker=marker))
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "core was invoked for a bibliography with no DOIs"


def test_core_reads_the_committed_bib_not_the_worktree(tmp_path):
    """The report must describe what would ship: the staged bib, not the file on disk."""
    marker = tmp_path / "core-was-called"
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Pulled \\cite{retracted2019}.")
    write(repo, "manuscript/references/library.bib", BIB)
    git(repo, "add", "-A")
    # Worktree-only edit: the retracted entry is gone from disk, but NOT from the index,
    # so a plain `git commit` still ships it and the guard must still report it.
    write(repo, "manuscript/references/library.bib",
          "@article{retracted2019, title={A Withdrawn Paper}, year={2019}}\n")

    result = run_guard(repo, env_with_core(tmp_path, marker=marker), command="git commit -m x")
    assert result.returncode == 0, result.stderr
    assert marker.exists()
    assert "retracted2019" in result.stderr
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert "10.1234/retracted-work" in payload["bib_text"], "core read the worktree, not the index"


def test_no_core_stderr_is_exactly_the_m1_stderr(tmp_path):
    """Without core, the guard is byte-for-byte the M1 guard: it says nothing extra."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Solid \\cite{good2020}.")
    write(repo, "manuscript/references/library.bib", BIB)
    git(repo, "add", "-A")
    result = run_guard(repo, env_without_core(tmp_path))
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# bib-validator: same flags, two engines
# ---------------------------------------------------------------------------

def test_validator_uses_core_when_available(tmp_path):
    bib = tmp_path / "library.bib"
    bib.write_text(BIB_WITH_GHOST, encoding="utf-8")

    result = run_validator(bib, env_with_core(tmp_path), "--check-doi", "--check-retracted")
    assert "engine: researcher-core" in result.stdout
    assert "EVIDENCE VERDICTS" in result.stdout
    # Axis (a): the invented entry is refusal-grade and is an error.
    assert "UNRESOLVABLE (axis a, refusal-grade)" in result.stdout
    # Axis (b): the retracted entry is an error in the validator a human runs on purpose.
    assert "RETRACTED (axis b)" in result.stdout
    assert result.returncode == 1


def test_validator_core_reports_inconclusive_as_a_warning_never_an_error(tmp_path):
    """A source that errored is not evidence of fabrication (D9): warn, never fail."""
    bib = tmp_path / "library.bib"
    bib.write_text(
        "@article{inconclusive2022, title={Single Index Only}, author={Solo, Sam},\n"
        "  journal={Journal of Tests}, year={2022}, doi={10.1234/inconclusive}}\n",
        encoding="utf-8",
    )
    result = run_validator(bib, env_with_core(tmp_path), "--check-doi", "--check-retracted")
    assert result.returncode == 0, result.stdout
    assert "inconclusive (axis a, not refusal-grade)" in result.stdout
    assert "ERRORS:" not in result.stdout


def test_validator_falls_back_without_core(tmp_path):
    """No core: the M1 CrossRef-only engine, same flags, no network needed for these."""
    bib = tmp_path / "library.bib"
    bib.write_text(BIB, encoding="utf-8")

    result = run_validator(bib, env_without_core(tmp_path), "--check-fields", "--check-duplicates")
    assert result.returncode == 0, result.stdout
    assert "DOI VERDICTS" in result.stdout  # the M1 block, not the core block
    assert "EVIDENCE VERDICTS" not in result.stdout
    assert "not-checked" in result.stdout


def test_validator_local_checks_are_identical_across_engines(tmp_path):
    """Duplicate keys and DOIs are local facts: both engines must find them and exit 1."""
    bib = tmp_path / "dupes.bib"
    bib.write_text(
        "@article{good2020, title={A Fine Paper}, year={2020}, doi={10.1234/fine}}\n"
        "@article{good2020, title={A Fine Paper Again}, year={2020}, doi={10.1234/fine}}\n",
        encoding="utf-8",
    )
    without = run_validator(bib, env_without_core(tmp_path), "--check-duplicates")
    with_core = run_validator(bib, env_with_core(tmp_path), "--check-duplicates", "--check-doi")

    assert without.returncode == with_core.returncode == 1
    for result in (without, with_core):
        assert "Duplicate citation key: good2020" in result.stdout
        assert "Duplicate DOI: 10.1234/fine" in result.stdout


def test_validator_broken_core_falls_back_silently(tmp_path):
    """An unrunnable core must not take the validator down: it just runs the M1 path."""
    bib = tmp_path / "library.bib"
    bib.write_text(BIB, encoding="utf-8")
    env = env_with_broken_core(tmp_path)

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(bib), "--check-fields", "--check-duplicates"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "DOI VERDICTS" in result.stdout


def test_researcher_core_off_forces_the_fallback(tmp_path):
    """The kill switch outranks a perfectly good RESEARCHER_CORE_CMD."""
    bib = tmp_path / "library.bib"
    bib.write_text(BIB, encoding="utf-8")
    env = env_with_core(tmp_path)
    env["RESEARCHER_CORE"] = "off"

    result = run_validator(bib, env, "--check-fields", "--check-duplicates")
    assert "EVIDENCE VERDICTS" not in result.stdout
    assert "DOI VERDICTS" in result.stdout


# ---------------------------------------------------------------------------
# The core bridge itself
# ---------------------------------------------------------------------------

def test_core_command_resolution(bib_validator, monkeypatch, tmp_path):
    monkeypatch.delenv("RESEARCHER_CORE", raising=False)
    monkeypatch.delenv("RESEARCHER_CORE_CMD", raising=False)

    # A project directory that does not exist means core is absent, full stop: the
    # resolver must not fall through to some other researcher_core on the machine.
    monkeypatch.setenv("RESEARCHER_CORE_PROJECT", str(tmp_path / "nope"))
    assert bib_validator.core_command() is None

    # A real project directory plus uv on PATH means the documented D3 invocation.
    project = tmp_path / "core"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    monkeypatch.setenv("RESEARCHER_CORE_PROJECT", str(project))
    monkeypatch.setattr(bib_validator.shutil, "which", lambda name: "uv" if name == "uv" else None)
    assert bib_validator.core_command() == [
        "uv", "run", "--project", str(project), "python", "-m", "researcher_core",
    ]

    # The kill switch wins over everything.
    monkeypatch.setenv("RESEARCHER_CORE", "off")
    assert bib_validator.core_command() is None


def test_run_core_never_raises(bib_validator, monkeypatch, tmp_path):
    """Every way core can fail is a None, which is the caller's cue to fall back."""
    monkeypatch.delenv("RESEARCHER_CORE", raising=False)
    monkeypatch.setenv("RESEARCHER_CORE_PROJECT", str(tmp_path / "nope"))

    monkeypatch.delenv("RESEARCHER_CORE_CMD", raising=False)
    assert bib_validator.run_core(["verify-bib", "x", "--json"]) is None  # no core

    monkeypatch.setenv("RESEARCHER_CORE_CMD", json.dumps(["definitely-not-an-executable-x9"]))
    assert bib_validator.run_core(["verify-bib", "x", "--json"]) is None  # OSError

    monkeypatch.setenv("RESEARCHER_CORE_CMD", json.dumps(
        [sys.executable, "-c", "import sys; sys.stdout.write('{');"]
    ))
    assert bib_validator.run_core(["verify-bib", "x", "--json"]) is None  # bad JSON

    monkeypatch.setenv("RESEARCHER_CORE_CMD", json.dumps(
        [sys.executable, "-c", "import time; time.sleep(5)"]
    ))
    assert bib_validator.run_core(["verify-bib", "x", "--json"], timeout=0.5) is None  # timeout


def test_run_core_trusts_the_report_not_the_exit_code(bib_validator, monkeypatch, tmp_path):
    """verify-bib exits non-zero BECAUSE it found problems. That report is the answer."""
    monkeypatch.delenv("RESEARCHER_CORE", raising=False)
    monkeypatch.setenv("RESEARCHER_CORE_PROJECT", str(tmp_path / "nope"))
    monkeypatch.setenv("RESEARCHER_CORE_CMD", json.dumps(
        [sys.executable, "-c",
         "import sys; sys.stdout.write('{\"entries\": [], \"summary\": {}}'); sys.exit(1)"]
    ))
    assert bib_validator.run_core(["verify-bib", "x", "--json"]) == {"entries": [], "summary": {}}


def test_core_findings_defends_against_a_thin_report(bib_validator):
    """A half-populated entry must not crash a hook, and must not lose refusal-grade."""
    report = {"entries": [
        {"key": "a", "verdict": "unresolvable"},  # refusal_grade flag missing entirely
        {"key": "b"},                             # no verdict at all
        "not-a-dict",
    ]}
    findings = bib_validator.core_findings(report)
    assert [f["key"] for f in findings] == ["a", "b"]
    assert findings[0]["refusal_grade"] is True  # inferred from the verdict, never dropped
    assert findings[1]["verdict"] == "inconclusive"
    assert findings[1]["refusal_grade"] is False


def test_fake_core_report_matches_the_committed_schema(tmp_path):
    """The wrapper is coded against core/schemas/verification-report.schema.json.

    If the fake drifted from the schema, these tests would be proving the wrapper reads a
    shape core never emits. jsonschema is a DEV dependency of core, so this check skips
    when it is not installed rather than adding a runtime dependency.
    """
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (REPO_ROOT / "core" / "schemas" / "verification-report.schema.json")
        .read_text(encoding="utf-8")
    )
    bib = tmp_path / "library.bib"
    bib.write_text(BIB_WITH_GHOST + BIB_WITH_WRONGDOI, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(FAKE_CORE), "verify-bib", str(bib), "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    report = json.loads(proc.stdout)
    jsonschema.validate(report, schema)


# ---------------------------------------------------------------------------
# The draft-integrity hook: never blocks, never goes to the network
# ---------------------------------------------------------------------------

def test_draft_hook_report_is_identical_with_and_without_core(tmp_path):
    root = tmp_path / "manuscript"
    (root / "references").mkdir(parents=True)
    (root / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\n"
        "Solid \\cite{good2020}. Ghost \\cite{missing2024}. See \\ref{fig:one}.\n"
        "\\label{fig:two}\n\\end{document}\n",
        encoding="utf-8",
    )
    (root / "references" / "library.bib").write_text(BIB, encoding="utf-8")

    without = run_draft_hook(root / "main.tex", env_without_core(tmp_path))
    with_core = run_draft_hook(root / "main.tex", env_with_core(tmp_path))

    assert without.returncode == 0
    assert with_core.returncode == 0
    assert "citations: 2 keys, 1 dangling -> missing2024" in without.stdout
    assert "cross-refs: 1 refs, 1 dangling -> fig:one" in without.stdout
    # The parser name is the only thing allowed to differ, and the findings must not.
    strip_header = lambda out: out.split("\n", 1)[1]  # noqa: E731
    assert strip_header(without.stdout) == strip_header(with_core.stdout)


def test_draft_hook_never_calls_core_over_the_network(tmp_path):
    """A PostToolUse hook fires on every edit: it must not shell out to core at all."""
    marker = tmp_path / "core-was-called"
    root = tmp_path / "manuscript"
    (root / "references").mkdir(parents=True)
    (root / "main.tex").write_text("\\cite{good2020}\n", encoding="utf-8")
    (root / "references" / "library.bib").write_text(BIB, encoding="utf-8")

    result = run_draft_hook(root / "main.tex", env_with_core(tmp_path, marker=marker))
    assert result.returncode == 0
    assert not marker.exists(), "the draft hook shelled out to core; it must stay local"


def test_draft_hook_phantom_comment_key_does_not_satisfy_a_cite(tmp_path):
    """@comment{foo, ...} is a skipped block, not an entry named foo. The regex reading
    this hook used to do would have let the phantom key satisfy \\cite{foo}."""
    root = tmp_path / "manuscript"
    (root / "references").mkdir(parents=True)
    (root / "main.tex").write_text("Phantom \\cite{foo}.\n", encoding="utf-8")
    (root / "references" / "library.bib").write_text(
        "@comment{foo, bar}\n@article{real2021, title={Real}, year={2021}}\n",
        encoding="utf-8",
    )
    result = run_draft_hook(root / "main.tex", env_without_core(tmp_path))
    assert result.returncode == 0
    assert "1 dangling -> foo" in result.stdout
