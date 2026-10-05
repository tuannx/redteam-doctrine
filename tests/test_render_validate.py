"""Regression tests for issue #8: render must validate before rendering.

A schema-invalid verdict (here: a negative counter) must never reach the
human-facing renderer as a PASS. verify already validates; render must
hold the same boundary (SPEC: validate verdict.json before any comment).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from pr_redteam.core import build_verdict

ROOT = Path(__file__).parent.parent


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _make_verdicts(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "fixture"
    subprocess.run(["git", "init", "-b", "main", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "app.py").write_text("def answer():\n    return 42\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_text("def answer():\n    return 43\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD")

    verdict = build_verdict(repo, base, head, "test", "render-validate")
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(verdict))
    verdict["counters"]["secretsFound"] = -1
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(verdict))
    return valid, invalid


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, "-m", "pr_redteam.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_render_rejects_schema_invalid_verdict(tmp_path: Path) -> None:
    valid, invalid = _make_verdicts(tmp_path)

    ok = _run_cli("render", "--verdict", str(valid))
    assert ok.returncode == 0
    assert "verdict: PASS" in ok.stdout

    bad = _run_cli("render", "--verdict", str(invalid))
    assert bad.returncode != 0
    assert "verdict: PASS" not in bad.stdout


def test_verify_still_rejects_schema_invalid_verdict(tmp_path: Path) -> None:
    _, invalid = _make_verdicts(tmp_path)
    bad = _run_cli("verify", "--verdict", str(invalid))
    assert bad.returncode != 0
