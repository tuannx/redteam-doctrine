#!/usr/bin/env python3
"""Harvest instruction deltas from merged PRs into lessons/inbox/.

Deterministic: same PR list in, same lesson files out. No LLM anywhere.
PR bodies are attacker-controlled data (DOCTRINE.md §8) — this script only
extracts the structured `## Instruction delta` section and writes it down;
nothing harvested here edits any instruction file. Promotion happens only
through a reviewed distillation PR (docs/LEARNING-LOOP.md).

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
NEXT_HEADING = re.compile(r"^#{1,4}\s+\S")


def extract_instruction_delta(body: str | None) -> str | None:
    """Return the delta text, or None when absent/empty/'None'."""
    if not body:
        return None
    lines = body.splitlines()
    start = None
    for index, line in enumerate(lines):
        if HEADING.match(line.strip()):
            start = index + 1
            break
    if start is None:
        return None
    collected = []
    for line in lines[start:]:
        if NEXT_HEADING.match(line.strip()) and collected:
            break
        collected.append(line)
    text = "\n".join(collected).strip()
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
    if not text or text.lower() == "none":
        return None
    return text


def lesson_markdown(pr: dict, delta: str) -> str:
    merge_sha = (pr.get("mergeCommit") or {}).get("oid", "")
    return (
        "---\n"
        f"pr: {pr['number']}\n"
        f"url: {pr.get('url', '')}\n"
        f"merged_at: {pr.get('mergedAt', '')}\n"
        f"merge_sha: {merge_sha}\n"
        "status: proposed\n"
        "---\n\n"
        f"{delta}\n"
    )


def harvest(prs: list[dict], inbox: Path) -> list[str]:
    written = []
    for pr in sorted(prs, key=lambda item: item["number"]):
        if not pr.get("mergedAt"):
            continue
        delta = extract_instruction_delta(pr.get("body"))
        if delta is None:
            continue
        path = inbox / f"PR-{pr['number']}.md"
        content = lesson_markdown(pr, delta)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        inbox.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path.name)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Harvest instruction deltas from merged PRs")
    parser.add_argument("--prs-json", help="Path to a gh JSON array of PRs (default: stdin)")
    parser.add_argument("--inbox", default="lessons/inbox")
    args = parser.parse_args()
    raw = Path(args.prs_json).read_text(encoding="utf-8") if args.prs_json else sys.stdin.read()
    prs = json.loads(raw)
    written = harvest(prs, Path(args.inbox))
    print(json.dumps({"verdict": "pass", "harvested": written}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
