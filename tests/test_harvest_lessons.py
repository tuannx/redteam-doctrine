import sys
from pathlib import Path

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
