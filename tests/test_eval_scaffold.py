"""The eval scaffold generates a passing, deterministic suite on the example app."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "skills" / "agent-eval-scaffold" / "templates"
APP_DIR = ROOT / "examples" / "two-agent-app"


def scaffold(target: Path) -> Path:
    """Materialize evals/ exactly the way the SKILL.md procedure prescribes."""
    evals = target / "evals"
    (evals / "datasets").mkdir(parents=True)
    (evals / "golden").mkdir()
    shutil.copy(TEMPLATES / "harness.py", evals / "harness.py")
    shutil.copy(TEMPLATES / "conftest.py", evals / "conftest.py")
    shutil.copy(TEMPLATES / "test_golden.py", evals / "test_golden.py")
    shutil.copy(TEMPLATES / "smoke.jsonl", evals / "datasets" / "smoke.jsonl")
    shutil.copy(TEMPLATES / "evals-README.md", evals / "README.md")
    workflows = target / ".github" / "workflows"
    workflows.mkdir(parents=True)
    shutil.copy(TEMPLATES / "evals-ci.yml", workflows / "evals.yml")
    return evals


@pytest.fixture()
def app_copy(tmp_path):
    target = tmp_path / "app"
    shutil.copytree(APP_DIR, target)
    scaffold(target)
    return target


def run_evals(target: Path, *extra):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "evals/", "-p", "no:cacheprovider", *extra],
        capture_output=True, text=True, cwd=target,
        env={"PATH": "/usr/bin:/bin"},
    )


def test_scaffold_seeds_then_passes_twice(app_copy):
    seed_run = run_evals(app_copy, "--update-golden")
    assert seed_run.returncode == 0, seed_run.stdout + seed_run.stderr
    goldens = list((app_copy / "evals" / "golden").glob("*.json"))
    assert len(goldens) == 3

    first = run_evals(app_copy)
    second = run_evals(app_copy)
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr


def test_golden_drift_fails(app_copy):
    assert run_evals(app_copy, "--update-golden").returncode == 0
    golden = sorted((app_copy / "evals" / "golden").glob("*.json"))[0]
    golden.write_text(golden.read_text().replace("summary", "SUMMARY"))
    result = run_evals(app_copy)
    assert result.returncode != 0
    assert "golden" in (result.stdout + result.stderr).lower()


def test_missing_golden_fails_with_hint(app_copy):
    result = run_evals(app_copy)
    assert result.returncode != 0
    assert "--update-golden" in result.stdout + result.stderr
