"""Regression tests for issue #4: renames must not bypass protected paths.

Renaming a file out of (or into) a protected directory used to report
protectedPathHits=0 because the human-readable numstat encodes renames
as "{old => new}/path". collect_diff_scope now parses the -z form, and
count_protected_path_hits examines both rename endpoints.
"""

import subprocess
from pathlib import Path

from pr_redteam.core import (
    build_verdict,
    collect_diff_scope,
    count_protected_path_hits,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    subprocess.run(["git", "init", "-b", "main", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / ".redteam").mkdir()
    (repo / ".redteam" / "policy.json").write_text("{}\n")
    (repo / "schema").mkdir()
    (repo / "schema" / "verdict.json").write_text("{}\n")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (repo / "public").mkdir()
    (repo / "public" / "policy.json").write_text("{}\n")
    (repo / "public" / "note.txt").write_text("note\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _hits(repo: Path, base: str, head: str) -> int:
    scope = collect_diff_scope(repo, base, head)
    return count_protected_path_hits(scope["files"])


def test_rename_out_of_protected_counts(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", ".redteam/policy.json", "public/moved.json")
    _git(repo, "commit", "-q", "-m", "rename out")
    head = _git(repo, "rev-parse", "HEAD")
    assert _hits(repo, base, head) == 1


def test_rename_into_protected_counts(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", "public/policy.json", ".redteam/imported.json")
    _git(repo, "commit", "-q", "-m", "rename in")
    head = _git(repo, "rev-parse", "HEAD")
    assert _hits(repo, base, head) == 1


def test_rename_workflow_out_counts(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", ".github/workflows/ci.yml", "public/ci.yml")
    _git(repo, "commit", "-q", "-m", "rename workflow out")
    head = _git(repo, "rev-parse", "HEAD")
    assert _hits(repo, base, head) == 1


def test_rename_between_protected_counts_once(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", "schema/verdict.json", ".redteam/verdict.json")
    _git(repo, "commit", "-q", "-m", "rename protected to protected")
    head = _git(repo, "rev-parse", "HEAD")
    assert _hits(repo, base, head) == 1


def test_clean_rename_and_edit_control(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", "public/note.txt", "public/note2.txt")
    _git(repo, "commit", "-q", "-m", "clean rename")
    head = _git(repo, "rev-parse", "HEAD")
    assert _hits(repo, base, head) == 0

    (repo / ".redteam" / "policy.json").write_text('{"v": 2}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "edit protected")
    head2 = _git(repo, "rev-parse", "HEAD")
    assert _hits(repo, head, head2) == 1


def test_rename_out_routes_to_maintainer_review(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "mv", ".redteam/policy.json", "public/moved.json")
    _git(repo, "commit", "-q", "-m", "rename out")
    head = _git(repo, "rev-parse", "HEAD")
    verdict = build_verdict(repo, base, head, "test", "rename-routing")
    assert verdict["counters"]["protectedPathHits"] == 1
    assert verdict["routing"]["maintainerReviewRequired"] is True
