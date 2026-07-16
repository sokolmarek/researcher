"""Tests for scripts/install-codex-skills.py.

The point of the installer is that an installed skill still works OUTSIDE the
plugin: no plugin-relative paths, no Claude-only frontmatter, no commands that
do not exist in Codex. These tests install into a temporary repo scope and
assert exactly that, including that every rewritten path resolves on disk.
"""

import re

import pytest

from conftest import load_script

codex = load_script("install-codex-skills")


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    repo = tmp_path_factory.mktemp("codex-target")
    codex.install(repo=str(repo))
    skills_root, shared = codex.targets(str(repo))
    return skills_root, shared


def test_installs_every_skill(installed):
    skills_root, _ = installed
    installed_dirs = sorted(p.name for p in skills_root.iterdir() if p.is_dir())
    expected = sorted(f"researcher-{p.name}" for p in codex.skill_dirs())
    assert installed_dirs == expected
    assert len(installed_dirs) == 35


def test_shared_assets_present(installed):
    _, shared = installed
    for name in ("references", "templates", "scripts"):
        assert (shared / name).is_dir()
    assert (shared / "references" / "integrity-constraints.md").exists()
    assert (shared / "references" / "figure-styles.md").exists()
    assert (shared / "scripts" / "bib-validator.py").exists()
    assert (shared / "scripts" / "latex-compile.py").exists()
    assert (shared / "scripts" / "latex_engine.py").exists()
    assert (shared / "scripts" / "install-git-hooks.py").exists()
    assert (shared / "AGENTS.md").exists()
    # The installer must not copy its own test suite into a user's skill tree.
    assert not (shared / "scripts" / "tests").exists()


def test_frontmatter_is_codex_compatible(installed):
    skills_root, _ = installed
    for skill in skills_root.iterdir():
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        match = codex.FRONTMATTER_RE.match(text)
        assert match, f"{skill.name}: no frontmatter"
        keys = [line.split(":", 1)[0].strip() for line in match.group(1).splitlines() if ":" in line]
        assert "name" in keys, f"{skill.name}: missing name"
        assert "description" in keys, f"{skill.name}: missing description"
        for banned in codex.CLAUDE_ONLY_KEYS:
            assert banned not in keys, f"{skill.name}: kept Claude-only key {banned}"


def test_fork_skills_lose_their_routing(installed):
    """implementation and code-analysis fork into code-agent under Claude. Codex has
    no subagents, so the frontmatter keys must be gone, the skill must survive, and
    the installed copy must say plainly that it now runs in the main session (its own
    prose still talks about the code-agent, which would otherwise mislead)."""
    skills_root, _ = installed
    for name in ("researcher-implementation", "researcher-code-analysis"):
        text = (skills_root / name / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = codex.FRONTMATTER_RE.match(text).group(1)
        assert "context:" not in frontmatter
        assert "agent:" not in frontmatter
        assert "Installed for Codex" in text, f"{name}: missing the runs-inline note"
        assert len(text.splitlines()) > 20, f"{name}: body was lost"


def test_forked_skill_description_drops_subagent_claim(installed):
    """Codex matches skills on the description, so it must not promise a subagent
    that does not exist there."""
    skills_root, _ = installed
    for name in ("researcher-implementation", "researcher-code-analysis"):
        text = (skills_root / name / "SKILL.md").read_text(encoding="utf-8")
        description = next(
            line for line in codex.FRONTMATTER_RE.match(text).group(1).splitlines()
            if line.startswith("description:")
        )
        lowered = description.lower()
        for claim in ("subagent", "code-agent", "sonnet", "opus"):
            assert claim not in lowered, f"{name} description still claims: {claim}"
        assert len(description) > 40, f"{name}: description was gutted"


def test_note_only_on_forked_skills(installed):
    skills_root, _ = installed
    noted = {s.name for s in skills_root.iterdir()
             if "Installed for Codex" in (s / "SKILL.md").read_text(encoding="utf-8")}
    assert noted == {"researcher-implementation", "researcher-code-analysis"}


def test_user_project_paths_survive(installed):
    """A skill names files it will CREATE in the user's project (scripts/train.py).
    Those are not plugin assets and must not be rewritten into the shared tree."""
    skills_root, shared = installed
    text = (skills_root / "researcher-implementation" / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/train.py" in text
    assert f"{shared.as_posix()}/scripts/train.py" not in text


def test_no_plugin_relative_paths_remain(installed):
    """A path like `references/foo.md` means nothing once the skill is installed
    outside the plugin, so every path that names a REAL plugin asset must have been
    rewritten to an absolute one. Paths that merely look similar but belong to the
    user's project (scripts/train.py) are expected to survive as they are."""
    skills_root, shared = installed
    offenders = []
    for skill in skills_root.iterdir():
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        for match in codex.ASSET_PATH_RE.finditer(text):
            already_absolute = text[:match.start()].endswith(shared.as_posix() + "/")
            is_plugin_asset = (codex.REPO_ROOT / match.group(0).rstrip(".,;:)`")).exists()
            if is_plugin_asset and not already_absolute:
                offenders.append(f"{skill.name}: {match.group(0)}")
    assert not offenders, "unrewritten plugin-relative paths: " + "; ".join(offenders[:10])


def test_every_referenced_asset_actually_exists(installed):
    """The whole point: a path the installed skill tells the model to read must
    resolve. This is the check that catches a broken rewrite."""
    skills_root, shared = installed
    pattern = re.compile(re.escape(shared.as_posix()) + r"/([A-Za-z0-9_./\-]+)")
    missing, checked = [], 0
    for skill in skills_root.iterdir():
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            relative = match.group(1).rstrip(".,;:)`")
            if not relative or relative.endswith("/"):
                continue
            checked += 1
            if not (shared / relative).exists():
                missing.append(f"{skill.name}: {relative}")
    assert checked > 0, "no shared-asset references found; the rewrite did nothing"
    assert not missing, "installed skills point at files that do not exist: " + "; ".join(sorted(set(missing))[:10])


def test_claude_commands_are_rewritten_to_codex_skills(installed):
    skills_root, _ = installed
    for skill in skills_root.iterdir():
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        assert "/researcher:" not in text, f"{skill.name}: kept a Claude command form"


def test_command_map_covers_every_command():
    """If a command is added to the plugin, the Codex mapping must learn about it."""
    commands = {p.stem for p in (codex.REPO_ROOT / "commands").glob("*.md")}
    assert commands == set(codex.COMMAND_TO_SKILL), (
        f"unmapped commands: {commands - set(codex.COMMAND_TO_SKILL)}; "
        f"stale entries: {set(codex.COMMAND_TO_SKILL) - commands}"
    )


def test_command_map_targets_real_skills():
    names = {p.name for p in codex.skill_dirs()}
    for command, skill in codex.COMMAND_TO_SKILL.items():
        assert skill in names, f"{command} maps to a skill that does not exist: {skill}"


def test_manuscript_paths_are_not_rewritten(installed):
    """`manuscript/references/library.bib` belongs to the USER's project. It must
    survive untouched, while the plugin's own `references/` is rewritten."""
    _, shared = installed
    text = "See `manuscript/references/library.bib` and `references/apa7-guide.md`."
    out = codex.rewrite(text, shared)
    assert "manuscript/references/library.bib" in out
    assert f"{shared.as_posix()}/references/apa7-guide.md" in out


def test_uninstall_is_clean(tmp_path):
    codex.install(repo=str(tmp_path))
    skills_root, shared = codex.targets(str(tmp_path))
    assert any(skills_root.iterdir())

    codex.uninstall(repo=str(tmp_path))
    assert not shared.exists()
    assert not [p for p in skills_root.iterdir() if p.name.startswith(codex.PREFIX)]


def test_install_is_idempotent(tmp_path):
    codex.install(repo=str(tmp_path))
    skills_root, _ = codex.targets(str(tmp_path))
    first = sorted(p.name for p in skills_root.iterdir())
    codex.install(repo=str(tmp_path))
    assert sorted(p.name for p in skills_root.iterdir()) == first
