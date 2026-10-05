#!/usr/bin/env python3
"""Harvest instruction deltas from merged PRs into lessons/inbox/.

Deterministic: same PR list in, same lesson files out. No LLM anywhere.
PR bodies are attacker-controlled data (DOCTRINE.md §8) — this script only
extracts text and writes it down; nothing harvested here edits any
instruction file. Promotion happens only through a reviewed distillation
PR (docs/LEARNING-LOOP.md).

Modes:
- default: only PRs carrying an `## Instruction delta` section teach.
- --backfill: PRs without that section contribute a *candidate* built from
  their Claim/Evidence sections (or the cleaned body when no such section
  exists), marked `status: proposed-backfill`. A human-reviewed
  distillation PR still decides what, if anything, becomes instruction.

Input: JSON array of PR objects (gh-compatible fields: number, url,
mergedAt, mergeCommit{oid}, body) via --prs-json or piped stdin.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^#{2,4}\s+Instruction delta\s*$", re.IGNORECASE)
SECTION = re.compile(r"^#{2,4}\s+(.+?)\s*$")
NEXT_HEADING = re.compile(r"^#{1,4}\s+\S")
COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
MAX_BACKFILL_CHARS = 2000


def _section(body: str, names: tuple[str, ...]) -> str | None:
    lines = body.splitlines()
    start = None
    wanted = {name.lower() for name in names}
    for index, line in enumerate(lines):
        match = SECTION.match(line.strip())
        if match and match.group(1).lower() in wanted:
            start = index + 1
            break
    if start is None:
        return None
    collected = []
    for line in lines[start:]:
        if NEXT_HEADING.match(line.strip()) and collected:
            break
        collected.append(line)
    text = COMMENTS.sub("", "\n".join(collected)).strip()
    return text or None


def extract_instruction_delta(body: str | None) -> str | None:
    """Return the delta text, or None when absent/empty/'None'."""
    if not body:
        return None
    text = _section(body, ("Instruction delta",))
    if not text or text.lower() == "none":
        return None
    return text


def extract_backfill_candidate(body: str | None) -> str | None:
    """Candidate lesson source for PRs that predate the delta field.

    Copies text verbatim (Claim/Evidence sections when present, else the
    cleaned body, bounded). Copies never summarize: distillation reviews it.
    """
    if not body:
        return None
    parts = []
    for names in (("Claim", "Mục đích"), ("Evidence", "Test")):
        section = _section(body, names)
        if section:
            parts.append(section)
    text = "\n\n".join(parts) if parts else COMMENTS.sub("", body).strip()
    text = text.strip()
    if not text:
        return None
    return text[:MAX_BACKFILL_CHARS]


def lesson_markdown(pr: dict, delta: str, source: str) -> str:
    merge_sha = (pr.get("mergeCommit") or {}).get("oid", "")
    status = "proposed" if source == "delta" else "proposed-backfill"
    return (
        "---\n"
        f"pr: {pr['number']}\n"
        f"url: {pr.get('url', '')}\n"
        f"merged_at: {pr.get('mergedAt', '')}\n"
        f"merge_sha: {merge_sha}\n"
        f"source: {source}\n"
        f"status: {status}\n"
        "---\n\n"
        f"{delta}\n"
    )


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    header, separator, _ = text[4:].partition("\n---\n")
    if not separator:
        return {}
    fields = {}
    for line in header.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


def harvest(prs: list[dict], inbox: Path, backfill: bool = False) -> list[str]:
    written = []
    for pr in sorted(prs, key=lambda item: item["number"]):
        if not pr.get("mergedAt"):
            continue
        body = pr.get("body")
        has_delta_section = any(HEADING.match(line.strip()) for line in (body or "").splitlines())
        delta = extract_instruction_delta(body)
        source = "delta"
        if delta is None and backfill and not has_delta_section:
            delta = extract_backfill_candidate(body)
            source = "backfill"
        path = inbox / f"PR-{pr['number']}.md"
        content = lesson_markdown(pr, delta or "", source)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            fields = _frontmatter(existing)
            if fields.get("status") in ("promoted", "rejected"):
                incoming = _frontmatter(content)
                for field in ("pr", "url", "merged_at", "merge_sha", "source"):
                    if field == "source" and delta is None:
                        continue
                    if field in fields and fields[field] != incoming[field]:
                        raise ValueError(f"{path.name}: reviewed lesson source conflict ({field})")
                print(
                    f"{path.name}: reviewed lesson preserved; "
                    "source-body comparison: notRun; owner review required",
                    file=sys.stderr,
                )
                continue
            if existing == content:
                continue
        if delta is None:
            continue
        inbox.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path.name)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest instruction deltas from merged PRs")
    parser.add_argument("--prs-json", help="Path to a gh JSON array of PRs (default: stdin)")
    parser.add_argument("--inbox", default="lessons/inbox")
    parser.add_argument("--backfill", action="store_true",
                        help="Also harvest Claim/Evidence candidates from PRs without a delta section")
    args = parser.parse_args()
    raw = Path(args.prs_json).read_text(encoding="utf-8") if args.prs_json else sys.stdin.read()
    prs = json.loads(raw)
    written = harvest(prs, Path(args.inbox), backfill=args.backfill)
    print(json.dumps({"verdict": "pass", "harvested": written}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
