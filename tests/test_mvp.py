import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from pr_redteam.core import build_verdict, hash_normalized_verdict

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "schema" / "verdict.schema.json").read_text()
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "main", "-q", str(tmp_path)], check=True)
    git(tmp_path, "config", "user.name", "fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    (tmp_path / "app.py").write_text("def answer():\n    return 42\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def commit_change(repo: Path, text: str) -> str:
    (repo / "app.py").write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "change")
    return git(repo, "rev-parse", "HEAD")


def test_clean_change_passes(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    head = commit_change(repo, "def answer():\n    return 43\n")
    verdict = build_verdict(repo, base, head, "test", "1")
    jsonschema.validate(verdict, SCHEMA)
    assert verdict["verdict"] == "pass"
    assert verdict["counters"]["unresolvedSymbols"] == 0
    assert verdict["counters"]["filesTouched"] == 1
    assert verdict["counters"]["netLocChanged"] == 0


def test_planted_invented_symbol_blocks(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    head = commit_change(repo, "def answer():\n    return missing_symbol()\n")
    verdict = build_verdict(repo, base, head, "test", "1")
    jsonschema.validate(verdict, SCHEMA)
    assert verdict["verdict"] == "block"
    assert verdict["counters"]["unresolvedSymbols"] == 1
    assert verdict["findings"][0]["gate"] == "unresolvedSymbols"


def test_planted_secret_blocks(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    fake_token = "ghp_" + "0" * 24 + "abcdefghij"
    (repo / "notes.txt").write_text(f"token {fake_token}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "leak")
    head = git(repo, "rev-parse", "HEAD")
    verdict = build_verdict(repo, base, head, "test", "1")
    assert verdict["verdict"] == "block"
    assert verdict["counters"]["secretsFound"] == 1


def test_double_run_hash_is_identical(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    head = commit_change(repo, "def answer():\n    return 44\n")
    first = hash_normalized_verdict(build_verdict(repo, base, head, "test", "1"))
    second = hash_normalized_verdict(build_verdict(repo, base, head, "test", "1"))
    assert first == second
