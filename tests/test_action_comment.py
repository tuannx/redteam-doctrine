"""Contract tests for the composite Action comment step (issue #15).

The gate step exits nonzero on BLOCK, so the comment step must opt out of
GitHub's default success-gating with always(), and must skip cleanly when
no verdict.json was produced. These tests scan action.yml as text so the
suite needs no YAML dependency.
"""

from pathlib import Path

ACTION = (Path(__file__).parent.parent / "action.yml").read_text()


def step_block(name: str) -> str:
    marker = f"- name: {name}"
    start = ACTION.index(marker)
    rest = ACTION[start + len(marker) :]
    nxt = rest.find("\n    - ")
    return rest if nxt == -1 else rest[:nxt]


def test_gate_step_still_surfaces_cli_exit_code():
    gate = step_block("Run gate")
    assert "exit $code" in gate


def test_comment_step_runs_even_when_gate_failed():
    comment = step_block("Comment verdict on PR")
    if_line = next(line for line in comment.splitlines() if "if:" in line)
    assert "always()" in if_line
    assert "inputs.comment == 'true'" in if_line
    assert "github.event_name == 'pull_request'" in if_line


def test_comment_step_skips_cleanly_without_verdict_file():
    comment = step_block("Comment verdict on PR")
    assert 'if [ ! -f "${{ inputs.verdict-path }}" ]' in comment
    assert "skipping comment" in comment
    # The guard must come before any render/comment command.
    assert comment.index("verdict-path") < comment.index("pr_redteam render")
