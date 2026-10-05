import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

from pr_redteam.core import (
    build_verdict,
    count_unresolved_symbols,
    hash_normalized_verdict,
    render_pr_comment_from_verdict,
)

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


@pytest.mark.parametrize("checkout", ["head", "base", "dirty", "missing", "dirty-config"])
def test_planted_invented_symbol_uses_pinned_head(repo: Path, checkout: str) -> None:
    base = git(repo, "rev-parse", "HEAD")
    head = commit_change(repo, "def answer():\n    return missing_symbol()\n")
    reference = build_verdict(repo, base, head, "test", "1")
    if checkout == "base":
        git(repo, "checkout", "-q", base)
    elif checkout == "dirty":
        (repo / "app.py").write_text("def answer():\n    return 43\n")
    elif checkout == "missing":
        (repo / "app.py").unlink()
    elif checkout == "dirty-config":
        (repo / "pyproject.toml").write_text(
            '[tool.ruff.lint.per-file-ignores]\n"app.py" = ["F821"]\n'
        )
    before = git(repo, "status", "--porcelain")
    checkout_head = git(repo, "rev-parse", "HEAD")

    verdict = build_verdict(repo, base, head, "test", "1")

    assert verdict["verdict"] == "block"
    assert verdict["counters"]["unresolvedSymbols"] == 1
    assert verdict["findings"][0]["file"] == "app.py"
    assert verdict["findings"][0]["line"] == 2
    assert hash_normalized_verdict(verdict) == hash_normalized_verdict(reference)
    assert git(repo, "status", "--porcelain") == before
    assert git(repo, "rev-parse", "HEAD") == checkout_head


@pytest.mark.parametrize("checkout", ["head", "base", "dirty", "missing"])
def test_clean_change_hash_uses_pinned_head(repo: Path, checkout: str) -> None:
    base = git(repo, "rev-parse", "HEAD")
    head = commit_change(repo, "def answer():\n    return 43\n")
    reference = build_verdict(repo, base, head, "test", "1")
    if checkout == "base":
        git(repo, "checkout", "-q", base)
    elif checkout == "dirty":
        (repo / "app.py").write_text("def answer():\n    return missing_symbol()\n")
    elif checkout == "missing":
        (repo / "app.py").unlink()
    before = git(repo, "status", "--porcelain")

    verdict = build_verdict(repo, base, head, "test", "1")

    assert verdict["verdict"] == "pass"
    assert verdict["counters"]["unresolvedSymbols"] == 0
    assert hash_normalized_verdict(verdict) == hash_normalized_verdict(reference)
    assert git(repo, "status", "--porcelain") == before


def test_added_python_file_is_checked_when_checkout_is_at_base(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    (repo / "added.py").write_text("def answer():\n    return missing_symbol()\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add source")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", base)

    count, findings = count_unresolved_symbols(repo, base, head)

    assert count == 1
    assert findings[0]["file"] == "added.py"
    assert not (repo / "added.py").exists()


def test_deleted_python_file_is_not_checked_in_old_checkout(repo: Path) -> None:
    base = commit_change(repo, "def answer():\n    return missing_symbol()\n")
    git(repo, "rm", "-q", "app.py")
    git(repo, "commit", "-q", "-m", "delete source")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", base)

    assert count_unresolved_symbols(repo, base, head) == (0, [])


def test_pinned_snapshot_preserves_git_blob_bytes(
    repo: Path, monkeypatch,
) -> None:
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "config", "core.autocrlf", "false")
    source = (
        "# coding: utf-8\r\n# café\r\ndef answer():\r\n"
        "    return missing_symbol()\r\n"
    ).encode("utf-8")
    configuration = b"# pinned configuration\r\n[lint]\r\nignore = []\r\n"
    (repo / "app.py").write_bytes(source)
    (repo / "ruff.toml").write_bytes(configuration)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "encoded source")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", base)
    original = subprocess.run
    checked = []

    def inspect_snapshot(command, **kwargs):
        if command[0] == "ruff":
            source_path = Path(command[-1])
            if not source_path.is_absolute():
                source_path = Path(kwargs["cwd"]) / source_path
            assert source_path.read_bytes() == source
            config = command[command.index("--config") + 1]
            assert Path(config).read_bytes() == configuration
            checked.append(True)
        return original(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", inspect_snapshot)

    count, findings = count_unresolved_symbols(repo, base, head)

    assert checked == [True]
    assert count == 1
    assert findings[0]["file"] == "app.py"


def test_non_utf8_pinned_python_file_is_not_silently_skipped(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_bytes(
        b"# coding: latin-1\n# caf\xe9\ndef answer():\n    return missing_symbol()\n"
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "non UTF-8 source")
    head = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", base)

    with pytest.raises(ValueError, match="unsupported pinned Python encoding"):
        count_unresolved_symbols(repo, base, head)


def test_pinned_ruff_configuration_preserves_suppression(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    (repo / "pyproject.toml").write_text(
        '[tool.ruff.lint.per-file-ignores]\n"app.py" = ["F821"]\n'
    )
    head = commit_change(repo, "def answer():\n    return missing_symbol()\n")
    (repo / "pyproject.toml").write_text("[tool.ruff.lint]\nignore = []\n")

    assert count_unresolved_symbols(repo, base, head) == (0, [])


def test_pinned_nested_ruff_configuration_extends_tracked_file(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    (repo / "src").mkdir()
    (repo / "config").mkdir()
    (repo / "config" / "defaults").write_text(
        '[lint.per-file-ignores]\n"bad.py" = ["F821"]\n'
    )
    (repo / "src" / "ruff.toml").write_text('extend = "../config/defaults"\n')
    (repo / "src" / "bad.py").write_text("def answer():\n    return missing_symbol()\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "nested config")
    head = git(repo, "rev-parse", "HEAD")
    (repo / "config" / "defaults").write_text("[lint]\nignore = []\n")

    assert count_unresolved_symbols(repo, base, head) == (0, [])


@pytest.mark.parametrize("configuration", ["outside", "symlink", "cycle"])
def test_ruff_configuration_must_stay_in_pinned_snapshot(
    repo: Path, configuration: str, monkeypatch,
) -> None:
    base = git(repo, "rev-parse", "HEAD")
    if configuration == "outside":
        outside = repo.parent / f"{repo.name}-outside.toml"
        outside.write_text('[lint]\nignore = ["F821"]\n')
        (repo / "ruff.toml").write_text(f'extend = "{outside}"\n')
    elif configuration == "symlink":
        (repo / "config.toml").write_text('[lint]\nignore = ["F821"]\n')
        (repo / "ruff.toml").symlink_to(repo / "config.toml")
    else:
        (repo / "ruff.toml").write_text('extend = "./second.toml"\n')
        (repo / "second.toml").write_text('extend = "./ruff.toml"\n')
    head = commit_change(repo, "def answer():\n    return missing_symbol()\n")
    original = subprocess.run

    def bounded_run(command, **kwargs):
        if command[0] == "ruff":
            kwargs["timeout"] = 1
        return original(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", bounded_run)

    with pytest.raises(ValueError):
        count_unresolved_symbols(repo, base, head)


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


def test_protected_path_requires_maintainer_review(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    (repo / "schema").mkdir()
    (repo / "schema" / "x.json").write_text("{}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "touch schema")
    head = git(repo, "rev-parse", "HEAD")
    verdict = build_verdict(repo, base, head, "test", "1")
    jsonschema.validate(verdict, SCHEMA)
    assert verdict["counters"]["protectedPathHits"] == 1
    assert verdict["counters"]["packagesTouched"] >= 1
    assert verdict["routing"]["maintainerReviewRequired"] is True


def test_agent_lane_is_recorded_and_not_self_merge_by_default(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    head = commit_change(repo, "def answer():\n    return 45\n")
    verdict = build_verdict(
        repo, base, head, "agent-app", "run-9", actor_kind="agent",
        agent_id="agent-1", task_id="task-7", attempt=1,
    )
    jsonschema.validate(verdict, SCHEMA)
    assert verdict["actor"]["kind"] == "agent"
    assert verdict["actor"]["agentId"] == "agent-1"
    assert verdict["routing"]["lane"] == "agent"
    assert verdict["routing"]["selfMergeEligible"] is False


def test_render_is_keyword_based(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    head = commit_change(repo, "def answer():\n    return 46\n")
    verdict = build_verdict(repo, base, head, "test", "1")
    comment = render_pr_comment_from_verdict(
        verdict, hash_normalized_verdict(verdict)
    )
    lines = comment.splitlines()
    assert lines[1] == "verdict: PASS"
    assert any(line.startswith("unresolvedSymbols: 0") for line in lines)
    assert any(line == "findings: none" for line in lines)
    assert any(line.startswith("nextAction: ") for line in lines)
    assert "|" not in comment
    assert "**" not in comment
