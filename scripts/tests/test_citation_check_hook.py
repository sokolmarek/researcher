"""Tests for scripts/citation-check-hook.py: prospective-commit-tree semantics."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "citation-check-hook.py"


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


MAIN_TEX = """\\documentclass{article}
\\begin{document}
\\input{introduction}
\\bibliographystyle{plain}
\\bibliography{references/library}
\\end{document}
"""


def run_guard(repo, command="git commit -m test"):
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(repo),
    })
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload, capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


def run_git_hook(repo):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--git-hook"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8",
        input="", timeout=60,
    )


def test_staged_ok(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Good \\cite{good2020}.")
    write(repo, "manuscript/references/library.bib",
          "@article{good2020, title={A}, year={2020}}")
    git(repo, "add", "-A")
    result = run_guard(repo)
    assert result.returncode == 0, result.stderr


def test_bibliography_entry_deletion_blocks(tmp_path):
    """Deleting a bib entry must flag citations in ALREADY-COMMITTED .tex files."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Good \\cite{good2020}.")
    write(repo, "manuscript/references/library.bib",
          "@article{good2020, title={A}, year={2020}}\n"
          "@article{other2021, title={B}, year={2021}}")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial")
    # Now stage a bib that DROPS good2020; the tex files are untouched.
    write(repo, "manuscript/references/library.bib",
          "@article{other2021, title={B}, year={2021}}")
    git(repo, "add", "manuscript/references/library.bib")
    result = run_guard(repo)
    assert result.returncode == 2
    assert "good2020" in result.stderr


def test_unstaged_unrelated_bib_does_not_satisfy(tmp_path):
    """An untracked .bib holding the key must not rescue the commit: it will not ship."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Bad \\cite{ghost2022}.")
    write(repo, "manuscript/references/library.bib",
          "@article{good2020, title={A}, year={2020}}")
    git(repo, "add", "-A")
    write(repo, "stray.bib", "@article{ghost2022, title={G}, year={2022}}")  # untracked
    result = run_guard(repo)
    assert result.returncode == 2
    assert "ghost2022" in result.stderr


def test_declared_bib_scoping_both_directions(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Cite \\cite{scoped2020}.")
    write(repo, "manuscript/references/library.bib",
          "@article{scoped2020, title={S}, year={2020}}")
    # A TRACKED but undeclared bib elsewhere holding a different key:
    write(repo, "other/other.bib", "@article{elsewhere2021, title={E}, year={2021}}")
    git(repo, "add", "-A")
    assert run_guard(repo).returncode == 0

    # Reverse: the cite is only satisfied by the undeclared bib -> must block.
    write(repo, "manuscript/introduction.tex", "Cite \\cite{elsewhere2021}.")
    git(repo, "add", "manuscript/introduction.tex")
    result = run_guard(repo)
    assert result.returncode == 2
    assert "elsewhere2021" in result.stderr


def test_commit_a_uses_worktree_content(tmp_path):
    """git commit -a stages tracked modifications: the guard must see the worktree
    version, not the stale index."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Fine.")
    write(repo, "manuscript/references/library.bib",
          "@article{good2020, title={A}, year={2020}}")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial")
    # Modify the tracked tex in the WORKTREE ONLY (not staged):
    write(repo, "manuscript/introduction.tex", "New \\cite{unseen2023}.")
    assert run_guard(repo, "git commit -m plain").returncode == 0  # plain commit: no staged change
    result = run_guard(repo, "git commit -am worktree")
    assert result.returncode == 2
    assert "unseen2023" in result.stderr


def test_section_file_resolves_via_root_declaration(tmp_path):
    """A section .tex with no own \\bibliography validates against the manuscript
    root's declaration (main.tex)."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/sections/methods.tex", "Deep \\cite{good2020}.")
    write(repo, "manuscript/references/library.bib",
          "@article{good2020, title={A}, year={2020}}")
    git(repo, "add", "-A")
    assert run_guard(repo).returncode == 0, "section file should use main.tex's declared bib"


def test_no_bib_anywhere_warns_not_blocks(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "notes.tex", "\\documentclass{article}\\begin{document}\\cite{x}\\end{document}")
    git(repo, "add", "-A")
    result = run_guard(repo)
    assert result.returncode == 0
    assert "no .bib" in result.stderr


def test_non_commit_command_passes_through(tmp_path):
    repo = make_repo(tmp_path)
    result = run_guard(repo, command="ls -la")
    assert result.returncode == 0
    assert result.stderr == ""


def test_git_hook_mode_blocks_with_exit_1(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Bad \\cite{missing2024}.")
    write(repo, "manuscript/references/library.bib",
          "@article{good2020, title={A}, year={2020}}")
    git(repo, "add", "-A")
    result = run_git_hook(repo)
    assert result.returncode == 1
    assert "missing2024" in result.stderr
