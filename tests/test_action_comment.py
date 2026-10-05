"""Composite Action shell regressions for issues #15, #23, and #24."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
ACTION = (ROOT / "action.yml").read_text()


def step_block(name: str) -> str:
    marker = f"- name: {name}"
    start = ACTION.index(marker)
    rest = ACTION[start + len(marker) :]
    nxt = rest.find("\n    - ")
    return rest if nxt == -1 else rest[:nxt]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _make_repo(tmp_path: Path, blocked: bool = False) -> tuple[Path, str, str]:
    repo = tmp_path / "fixture"
    subprocess.run(["git", "init", "-b", "main", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "notes.txt").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    fake_token = "ghp_" + "0" * 24 + "abcdefghij"
    (repo / "notes.txt").write_text(fake_token + "\n" if blocked else "head\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "head")
    return repo, base, _git(repo, "rev-parse", "HEAD")


def _shell_env(repo: Path, base: str, head: str) -> dict[str, str]:
    bin_dir = repo.parent / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "pr_redteam"
    wrapper.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" -m pr_redteam.cli "$@"\n'
    )
    wrapper.chmod(0o755)
    (bin_dir / "python3").symlink_to(sys.executable)
    gh = bin_dir / "gh"
    gh.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> gh-stub.log\n'
        'cp comment.md gh-stub-body.md\n'
    )
    gh.chmod(0o755)
    return dict(
        os.environ,
        PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
        PYTHONPATH=str(ROOT),
        BASE_SHA=base,
        HEAD_SHA=head,
        VERDICT_PATH="verdict.json",
        GITHUB_OUTPUT=str(repo / "github-output.txt"),
        VERDICT="",
    )


def _run_step(name: str, repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    body = step_block(name).split("      run: |\n", 1)[1]
    lines = []
    for line in body.splitlines():
        if line and not line.startswith("        "):
            break
        lines.append(line[8:] if line else "")
    script = "\n".join(lines)
    for key, value in {
        "inputs.base": env["BASE_SHA"],
        "inputs.head": env["HEAD_SHA"],
        "inputs.verdict-path": env["VERDICT_PATH"],
        "github.event.pull_request.number": "42",
    }.items():
        script = script.replace("${{ " + key + " }}", value)
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        cwd=repo, env=env, capture_output=True, text=True,
    )


@pytest.mark.parametrize("blocked", [False, True])
def test_gate_exit_matches_verdict_and_preserves_comment(tmp_path: Path, blocked: bool):
    repo, base, head = _make_repo(tmp_path, blocked)
    env = _shell_env(repo, base, head)
    gate = _run_step("Run gate", repo, env)
    assert gate.returncode == (2 if blocked else 0), gate.stderr
    verdict = json.loads((repo / "verdict.json").read_text())
    word = "block" if blocked else "pass"
    assert verdict["verdict"] == word
    assert verdict["pr"] == {"baseSha": base, "headSha": head}
    assert (repo / "github-output.txt").read_text() == f"verdict={word}\n"
    env["VERDICT"] = word
    comment = _run_step("Comment verdict on PR", repo, env)
    assert comment.returncode == 0, comment.stderr
    assert f"verdict: {word.upper()}" in (repo / "gh-stub-body.md").read_text()


def test_gate_failure_discards_preexisting_verdict(tmp_path: Path):
    repo, base, head = _make_repo(tmp_path)
    env = _shell_env(repo, base, head)
    ok = _run_step("Run gate", repo, env)
    assert ok.returncode == 0, ok.stderr
    (repo / "github-output.txt").unlink()
    env["HEAD_SHA"] = "f" * 40
    bad = _run_step("Run gate", repo, env)
    assert bad.returncode != 0
    assert not (repo / "verdict.json").exists()
    assert not (repo / "github-output.txt").exists()
    comment = _run_step("Comment verdict on PR", repo, env)
    assert comment.returncode == 0
    assert not (repo / "gh-stub.log").exists()


@pytest.mark.parametrize("blocked", [False, True])
def test_gate_accepts_exit_two_only_for_block(tmp_path: Path, blocked: bool):
    repo, base, head = _make_repo(tmp_path, blocked)
    env = _shell_env(repo, base, head)
    wrapper = repo.parent / "bin" / "pr_redteam"
    wrapper.write_text(
        f'#!/bin/sh\n"{sys.executable}" -m pr_redteam.cli "$@"\n'
        'code=$?\nif [ "$1" = run ] && [ "$code" -eq 0 ]; then\n'
        '  exit 2\nfi\nexit "$code"\n'
    )
    gate = _run_step("Run gate", repo, env)
    assert gate.returncode == 2, gate.stderr
    assert (repo / "verdict.json").exists() is blocked
    assert (repo / "github-output.txt").exists() is blocked


@pytest.mark.parametrize("tamper", ["sha", "schema"])
def test_gate_rejects_invalid_produced_verdict(tmp_path: Path, tamper: str):
    repo, base, head = _make_repo(tmp_path)
    env = _shell_env(repo, base, head)
    mutation = (
        f'verdict["pr"]["headSha"] = "{base}"'
        if tamper == "sha" else 'verdict["counters"]["secretsFound"] = -1'
    )
    wrapper = repo.parent / "bin" / "pr_redteam"
    wrapper.write_text(
        f'#!/bin/sh\n"{sys.executable}" -m pr_redteam.cli "$@"\n'
        'code=$?\nif [ "$1" = run ]; then\n'
        f'"{sys.executable}" - "$VERDICT_PATH" <<\'PY\'\n'
        'import json\nimport sys\nfrom pathlib import Path\n'
        'path = Path(sys.argv[1])\nverdict = json.loads(path.read_text())\n'
        + mutation + '\npath.write_text(json.dumps(verdict))\nPY\nfi\nexit "$code"\n'
    )
    gate = _run_step("Run gate", repo, env)
    assert gate.returncode != 0
    assert not (repo / "verdict.json").exists()
    assert not (repo / "github-output.txt").exists()


@pytest.mark.parametrize("tamper", ["sha", "word", "schema"])
def test_comment_rejects_changed_verdict(tmp_path: Path, tamper: str):
    repo, base, head = _make_repo(tmp_path)
    env = _shell_env(repo, base, head)
    gate = _run_step("Run gate", repo, env)
    assert gate.returncode == 0, gate.stderr
    path = repo / "verdict.json"
    verdict = json.loads(path.read_text())
    if tamper == "sha":
        verdict["pr"]["headSha"] = base
    elif tamper == "word":
        verdict["verdict"] = "block"
    else:
        verdict["counters"]["secretsFound"] = -1
    path.write_text(json.dumps(verdict))
    env["VERDICT"] = "pass"
    comment = _run_step("Comment verdict on PR", repo, env)
    assert comment.returncode != 0
    assert not (repo / "gh-stub.log").exists()


def test_comment_step_runs_even_when_gate_failed():
    comment = step_block("Comment verdict on PR")
    if_line = next(line for line in comment.splitlines() if "if:" in line)
    assert "always()" in if_line
    assert "inputs.comment == 'true'" in if_line
    assert "github.event_name == 'pull_request'" in if_line
    assert "steps.gate.outputs.verdict != ''" in if_line


def test_comment_step_skips_cleanly_without_verdict_file():
    comment = step_block("Comment verdict on PR")
    assert 'if [ ! -f "$VERDICT_PATH" ]' in comment
    assert "skipping comment" in comment
    # The guard must come before any render/comment command.
    assert comment.index("skipping comment") < comment.index("pr_redteam render")
