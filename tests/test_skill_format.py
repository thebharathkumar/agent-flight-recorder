"""Every SKILL.md parses, triggers properly, and only references files that exist."""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIRS = sorted(p.parent for p in (ROOT / "skills").glob("*/SKILL.md"))
EXPECTED_SKILLS = {"audit-log", "otel-agent-tracing", "agent-eval-scaffold", "trace-triage"}

REFERENCE_PATTERN = re.compile(
    r"\b((?:scripts|templates|assets|references)/[A-Za-z0-9_.\-/]+)"
)


def frontmatter(skill_dir: Path) -> dict:
    text = (skill_dir / "SKILL.md").read_text()
    assert text.startswith("---\n"), f"{skill_dir.name}: missing frontmatter"
    _, block, _ = text.split("---\n", 2)
    return yaml.safe_load(block)


def test_all_four_skills_present():
    assert {d.name for d in SKILL_DIRS} == EXPECTED_SKILLS


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda d: d.name)
def test_frontmatter_fields(skill_dir):
    meta = frontmatter(skill_dir)
    assert meta["name"] == skill_dir.name
    description = meta["description"]
    assert "Use when" in description, "description needs an explicit trigger clause"
    assert len(description) <= 1024


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda d: d.name)
def test_referenced_files_exist(skill_dir):
    body = (skill_dir / "SKILL.md").read_text()
    references = set(REFERENCE_PATTERN.findall(body))
    assert references, f"{skill_dir.name}: SKILL.md references no bundled files"
    for ref in references:
        target = skill_dir / ref.rstrip(".")
        assert target.exists(), f"{skill_dir.name}: SKILL.md references missing {ref}"


@pytest.mark.parametrize("skill_dir", SKILL_DIRS, ids=lambda d: d.name)
def test_bundled_files_are_mentioned(skill_dir):
    """Inverse check: every bundled script and template appears in its SKILL.md."""
    body = (skill_dir / "SKILL.md").read_text()
    for sub in ("scripts", "templates"):
        for file in (skill_dir / sub).glob("*"):
            if file.is_file():
                assert file.name in body, (
                    f"{skill_dir.name}: bundled {sub}/{file.name} never mentioned in SKILL.md"
                )
