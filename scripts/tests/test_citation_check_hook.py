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


def test_staged_only_dangling_cite_with_clean_worktree(tmp_path):
    """The index, not the worktree, is what ships: a dangling cite that exists ONLY in
    the staged version must block even though the worktree file is clean."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Good \\cite{good2020}.")
    write(repo, "manuscript/references/library.bib",
          "@article{good2020, title={A}, year={2020}}")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial")

    # Stage a bad version, then restore the worktree copy to the clean text.
    write(repo, "manuscript/introduction.tex", "Good \\cite{good2020}. New \\cite{stagedonly2099}.")
    git(repo, "add", "manuscript/introduction.tex")
    write(repo, "manuscript/introduction.tex", "Good \\cite{good2020}.")

    result = run_guard(repo)
    assert result.returncode == 2, result.stderr
    assert "stagedonly2099" in result.stderr


def test_unrelated_manuscript_dangling_cite_does_not_block(tmp_path):
    """Scoping is by manuscript root: a pre-existing dangling key in manuscript-b must
    not block a commit that only touches manuscript-a."""
    repo = make_repo(tmp_path)
    for name in ("manuscript-a", "manuscript-b"):
        write(repo, f"{name}/main.tex", MAIN_TEX)
    write(repo, "manuscript-a/introduction.tex", "Fine \\cite{alpha2020}.")
    write(repo, "manuscript-a/references/library.bib",
          "@article{alpha2020, title={A}, year={2020}}")
    # manuscript-b ships a dangling citation of its own.
    write(repo, "manuscript-b/introduction.tex", "Broken \\cite{betaghost2099}.")
    write(repo, "manuscript-b/references/library.bib",
          "@article{beta2021, title={B}, year={2021}}")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "initial")

    # Touch manuscript-a only. manuscript-b is not in scope, so its rot is not ours.
    write(repo, "manuscript-a/introduction.tex", "Fine \\cite{alpha2020}. Still fine.")
    git(repo, "add", "manuscript-a/introduction.tex")

    result = run_guard(repo)
    assert result.returncode == 0, result.stderr
    assert "betaghost2099" not in result.stderr

    # Sanity check the other direction: touching manuscript-b DOES surface its key.
    write(repo, "manuscript-b/introduction.tex", "Broken \\cite{betaghost2099}. Edited.")
    git(repo, "add", "manuscript-b/introduction.tex")
    result = run_guard(repo)
    assert result.returncode == 2
    assert "betaghost2099" in result.stderr


def test_commented_out_bib_entry_does_not_satisfy_cite(tmp_path):
    """A %-commented-out entry is invisible to BibTeX, so it must not satisfy a cite."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Stale \\cite{old2020}.")
    write(repo, "manuscript/references/library.bib",
          "% @article{old2020, title={Retired}, year={2020}}\n"
          "@article{new2021, title={Current}, year={2021}}\n")
    git(repo, "add", "-A")
    result = run_guard(repo)
    assert result.returncode == 2, result.stderr
    assert "old2020" in result.stderr


def test_comment_block_key_does_not_satisfy_cite(tmp_path):
    """@comment{foo, bar} is a skipped block, not an entry named foo: a regex key
    scanner would let the phantom key satisfy \\cite{foo}."""
    repo = make_repo(tmp_path)
    write(repo, "manuscript/main.tex", MAIN_TEX)
    write(repo, "manuscript/introduction.tex", "Phantom \\cite{foo}.")
    write(repo, "manuscript/references/library.bib",
          "@comment{foo, bar}\n"
          "@article{real2021, title={Real}, year={2021}}\n")
    git(repo, "add", "-A")
    result = run_guard(repo)
    assert result.returncode == 2, result.stderr
    assert "foo" in result.stderr


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
