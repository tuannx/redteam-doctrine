import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from harvest_lessons import extract_instruction_delta, harvest  # noqa: E402

BODY = """## Claim

Fix the thing.

## Instruction delta

- Read changed files from the pinned head blob, never the working checkout.
  Evidence: unresolvedSymbols counter; verdict hash stable across runs.

## Notes

Something else.
"""


def test_extracts_delta_until_next_heading():
    delta = extract_instruction_delta(BODY)
    assert delta.startswith("- Read changed files")
    assert "Something else" not in delta


def test_none_and_missing_sections_teach_nothing():
    assert extract_instruction_delta("## Instruction delta\n\nNone\n") is None
    assert extract_instruction_delta("no sections here") is None
    assert extract_instruction_delta(None) is None
    assert extract_instruction_delta("## Instruction delta\n<!-- comment -->\n") is None


def test_harvest_writes_only_merged_prs_with_deltas(tmp_path):
    prs = [
        {"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
         "mergeCommit": {"oid": "abc"}, "body": BODY},
        {"number": 10, "url": "u10", "mergedAt": None,
         "mergeCommit": None, "body": BODY},
        {"number": 11, "url": "u11", "mergedAt": "2026-10-05T01:00:00Z",
         "mergeCommit": {"oid": "def"}, "body": "## Instruction delta\n\nNone\n"},
    ]
    written = harvest(prs, tmp_path)
    assert written == ["PR-9.md"]
    content = (tmp_path / "PR-9.md").read_text(encoding="utf-8")
    assert "status: proposed" in content and "merge_sha: abc" in content
    # Deterministic: a second run writes nothing.
    assert harvest(prs, tmp_path) == []


PLAIN_BODY = "unresolvedSymbols read changed files from the mutable checkout.\n\nRead changed Python blobs from the pinned head instead."


def test_backfill_copies_plain_body_verbatim(tmp_path):
    prs = [{"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
            "mergeCommit": {"oid": "abc"}, "body": PLAIN_BODY}]
    assert harvest(prs, tmp_path) == []
    written = harvest(prs, tmp_path, backfill=True)
    assert written == ["PR-9.md"]
    content = (tmp_path / "PR-9.md").read_text(encoding="utf-8")
    assert "status: proposed-backfill" in content and "mutable checkout" in content


def test_backfill_skips_empty_bodies_and_prefers_delta(tmp_path):
    prs = [
        {"number": 1, "url": "u1", "mergedAt": "2026-10-03T00:00:00Z",
         "mergeCommit": {"oid": "a"}, "body": "  \n<!-- only a comment -->\n"},
        {"number": 2, "url": "u2", "mergedAt": "2026-10-03T00:00:00Z",
         "mergeCommit": {"oid": "b"}, "body": BODY},
    ]
    written = harvest(prs, tmp_path, backfill=True)
    assert written == ["PR-2.md"]
    assert "source: delta" in (tmp_path / "PR-2.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("status", ["promoted", "rejected"])
@pytest.mark.parametrize("include_source", [False, True])
def test_repeat_harvest_preserves_reviewed_lesson_and_reason(tmp_path, capsys, status, include_source):
    prs = [{"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
            "mergeCommit": {"oid": "abc"}, "body": BODY}]
    harvest(prs, tmp_path)
    path = tmp_path / "PR-9.md"
    reviewed = path.read_text(encoding="utf-8").replace(
        "status: proposed", f"status: {status}"
    ) + "\nOwner-reviewed reason: this decision remains recorded.\n"
    if not include_source:
        reviewed = reviewed.replace("source: delta\n", "")
    reviewed_bytes = reviewed.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(reviewed_bytes)

    assert harvest(prs, tmp_path) == []
    assert path.read_bytes() == reviewed_bytes
    assert "source-body comparison: notRun; owner review required" in capsys.readouterr().err


@pytest.mark.parametrize("status", ["promoted", "rejected"])
def test_changed_reviewed_body_is_preserved_with_advisory(tmp_path, capsys, status):
    pr = {"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
          "mergeCommit": {"oid": "abc"}, "body": BODY}
    harvest([pr], tmp_path)
    path = tmp_path / "PR-9.md"
    reviewed = path.read_text(encoding="utf-8").replace(
        "status: proposed", f"status: {status}"
    ) + "\nOwner-reviewed reason: this decision remains recorded.\n"
    path.write_text(reviewed, encoding="utf-8")
    pr["body"] = BODY.replace("pinned head blob", "mutable checkout")

    assert harvest([pr], tmp_path) == []
    assert path.read_text(encoding="utf-8") == reviewed
    assert "source-body comparison: notRun; owner review required" in capsys.readouterr().err


@pytest.mark.parametrize("status", ["promoted", "rejected"])
@pytest.mark.parametrize("field", ["url", "mergedAt", "mergeCommit"])
def test_changed_reviewed_metadata_reports_conflict_without_overwrite(tmp_path, status, field):
    pr = {"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
          "mergeCommit": {"oid": "abc"}, "body": BODY}
    harvest([pr], tmp_path)
    path = tmp_path / "PR-9.md"
    reviewed = path.read_text(encoding="utf-8").replace(
        "status: proposed", f"status: {status}"
    ) + "\nOwner-reviewed reason: this decision remains recorded.\n"
    path.write_text(reviewed, encoding="utf-8")
    pr[field] = {"oid": "def"} if field == "mergeCommit" else "changed"

    with pytest.raises(ValueError, match="PR-9.*conflict"):
        harvest([pr], tmp_path)
    assert path.read_text(encoding="utf-8") == reviewed


def test_changed_reviewed_source_kind_reports_conflict_without_overwrite(tmp_path):
    pr = {"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
          "mergeCommit": {"oid": "abc"}, "body": PLAIN_BODY}
    harvest([pr], tmp_path, backfill=True)
    path = tmp_path / "PR-9.md"
    reviewed = path.read_text(encoding="utf-8").replace(
        "status: proposed-backfill", "status: promoted"
    ) + "\nOwner-reviewed reason: this decision remains recorded.\n"
    path.write_text(reviewed, encoding="utf-8")
    pr["body"] = BODY

    with pytest.raises(ValueError, match="PR-9.*conflict"):
        harvest([pr], tmp_path, backfill=True)
    assert path.read_text(encoding="utf-8") == reviewed


def test_reviewed_pr_identity_conflict_is_not_overwritten(tmp_path):
    prs = [{"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
            "mergeCommit": {"oid": "abc"}, "body": BODY}]
    harvest(prs, tmp_path)
    path = tmp_path / "PR-9.md"
    reviewed = path.read_text(encoding="utf-8").replace(
        "status: proposed", "status: rejected"
    ).replace("pr: 9", "pr: 10")
    path.write_text(reviewed, encoding="utf-8")

    with pytest.raises(ValueError, match="PR-9.*conflict.*pr"):
        harvest(prs, tmp_path)
    assert path.read_text(encoding="utf-8") == reviewed


def test_explicit_none_does_not_silently_skip_reviewed_source_advisory(tmp_path, capsys):
    pr = {"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
          "mergeCommit": {"oid": "abc"}, "body": BODY}
    harvest([pr], tmp_path)
    path = tmp_path / "PR-9.md"
    reviewed = path.read_text(encoding="utf-8").replace(
        "status: proposed", "status: promoted"
    ) + "\nOwner-reviewed reason: this decision remains recorded.\n"
    path.write_text(reviewed, encoding="utf-8")
    pr["body"] = "## Instruction delta\n\nNone\n"

    assert harvest([pr], tmp_path, backfill=True) == []
    assert path.read_text(encoding="utf-8") == reviewed
    assert "source-body comparison: notRun; owner review required" in capsys.readouterr().err


@pytest.mark.parametrize("backfill", [False, True])
def test_explicit_none_teaches_nothing_even_with_backfill(tmp_path, backfill):
    prs = [{"number": 9, "url": "u9", "mergedAt": "2026-10-05T00:22:10Z",
            "mergeCommit": {"oid": "abc"},
            "body": "## Claim\nHistorical claim.\n\n## Instruction delta\n\nNone\n"}]

    assert harvest(prs, tmp_path, backfill=backfill) == []
    assert list(tmp_path.iterdir()) == []
