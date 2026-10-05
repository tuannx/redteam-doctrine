"""Regression locks for issues #6 and #7 (closed as already-fixed).

Both claims were verified invalid on current main by the First Mate
sweep (2026-10-05), but nothing in the suite guarded the behavior. These
tests drive the real CLI so an incidental refactor cannot silently
reopen either hole:

- #6: a Ruff configuration error (exit 2) must fail the gate, never PASS.
- #7: default, relative, and absolute --repo forms must produce
  identical verdicts on the same fixture.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _init_repo(tmp_path: Path, name: str, head_text: str, extra: dict | None = None) -> tuple[Path, str, str]:
    repo = tmp_path / name
    subprocess.run(["git", "init", "-b", "main", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "app.py").write_text("def answer():\n    return 42\n")
    for rel, text in (extra or {}).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_text(head_text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD")
    return repo, base, head


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, "-m", "pr_redteam.cli", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )


BAD = "def answer():\n    return missing_symbol\n"


def test_ruff_config_error_never_passes(tmp_path: Path) -> None:
    repo, base, head = _init_repo(
        tmp_path, "cfg", BAD, extra={"ruff.toml": 'target-version = "py999"\n'}
    )
    out = tmp_path / "verdict.json"
    result = _run_cli(
        ["run", "--repo", str(repo), "--base", base, "--head", head, "--out", str(out)],
        cwd=tmp_path,
    )
    assert result.returncode != 0
    if out.exists():
        assert json.loads(out.read_text())["verdict"] != "pass"


def test_repo_path_forms_produce_identical_verdicts(tmp_path: Path) -> None:
    repo, base, head = _init_repo(tmp_path, "paths", BAD)
    forms = [
        (["run", "--base", base, "--head", head], repo),
        (["run", "--repo", ".", "--base", base, "--head", head], repo),
        (["run", "--repo", str(repo), "--base", base, "--head", head], tmp_path),
    ]
    outputs = []
    for index, (args, cwd) in enumerate(forms):
        out = tmp_path / f"verdict-{index}.json"
        result = _run_cli([*args, "--out", str(out)], cwd=cwd)
        assert result.returncode == 0, result.stderr
        outputs.append((result.stdout.strip(), json.loads(out.read_text())))
    hashes = {item[0] for item in outputs}
    assert len(hashes) == 1
    for _, verdict in outputs:
        assert verdict["verdict"] == "block"
        assert verdict["counters"]["unresolvedSymbols"] == 1
