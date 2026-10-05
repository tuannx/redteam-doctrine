#!/usr/bin/env python3
"""Fetch a maintainer-pattern corpus from a GitHub repo (deterministic stage 1).

Collects merged PRs, inline review comments, and review bodies into one
JSON file. No analysis here — extraction is a separate, reviewed step
(doctrine: miners draft, gates decide). Bots are kept but flagged so the
analyst can exclude them deliberately rather than by accident.

Usage:
  python3 scripts/fetch_review_corpus.py --repo owner/name --out corpus.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def gh_api(path: str) -> list:
    result = subprocess.run(
        ["gh", "api", "--paginate", path],
        capture_output=True, text=True, check=True,
    )
    items: list = []
    # --paginate concatenates JSON arrays/pages; decode stream of values.
    decoder = json.JSONDecoder()
    text = result.stdout.strip()
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        value, index = decoder.raw_decode(text, index)
        items.extend(value if isinstance(value, list) else [value])
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch merged PRs + review activity corpus")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    merged = gh_api(f"repos/{args.repo}/pulls?state=closed&per_page=100")
    merged = [pr for pr in merged if pr.get("merged_at")]
    comments = gh_api(f"repos/{args.repo}/pulls/comments?per_page=100")
    reviews = []
    # Reviews need per-PR calls; fetch for each merged PR (bounded).
    for pr in merged:
        for review in gh_api(f"repos/{args.repo}/pulls/{pr['number']}/reviews?per_page=100"):
            review["_pr"] = pr["number"]
            reviews.append(review)

    def is_bot(login: str) -> bool:
        return login.endswith("[bot]") or login in {"Copilot"}

    corpus = {
        "repo": args.repo,
        "merged_prs": [
            {"number": pr["number"], "title": pr["title"], "author": pr["user"]["login"],
             "merged_at": pr["merged_at"], "url": pr["html_url"]}
            for pr in sorted(merged, key=lambda item: item["number"])
        ],
        "review_comments": [
            {"pr": int(c["pull_request_url"].rstrip("/").split("/")[-1]),
             "author": c["user"]["login"], "bot": is_bot(c["user"]["login"]),
             "path": c.get("path"), "created_at": c["created_at"], "body": c.get("body", "")}
            for c in comments
        ],
        "reviews": [
            {"pr": r.get("_pr", 0), "author": r["user"]["login"], "bot": is_bot(r["user"]["login"]),
             "state": r.get("state"), "submitted_at": r.get("submitted_at"), "body": r.get("body", "")}
            for r in reviews
        ],
    }
    # Attach PR numbers to reviews (endpoint returns per-PR lists in order).
    Path(args.out).write_text(json.dumps(corpus, indent=1, ensure_ascii=False), encoding="utf-8")
    humans = [c for c in corpus["review_comments"] if not c["bot"]]
    print(json.dumps({"repo": args.repo, "merged_prs": len(corpus["merged_prs"]),
                      "review_comments": len(corpus["review_comments"]),
                      "human_review_comments": len(humans)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
