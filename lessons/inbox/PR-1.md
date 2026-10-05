---
pr: 1
url: https://github.com/tuannx/redteam-doctrine/pull/1
merged_at: 2026-10-03T14:20:12Z
merge_sha: 07d18a7321fbf5f2090a83f5368db19e3af9b409
source: backfill
status: proposed-backfill
---

1. MVP pr_redteam step 1: diff counters, ruff F821, secret patterns, schema-valid verdict.json, normalized hash, comment renderer.
2. Align cho 3 nhóm decision điểm cao nhất từ bộ 100 cases:
   - **G. AI-Generated Code Gate (#61-70)**
   - **A. PR & CI Merge Gate (#1-10)**
   - **E. Monorepo & OSS Maintainer (#41-50)**

Ba nhóm là 1 pipeline: agent sinh code -> PR/CI chặn cổng -> maintainer chỉ xem ngoại lệ.

`PATH=$PWD/.venv/bin:$PATH .venv/bin/python -m pytest tests/ -q` -> **7 passed**
Fixtures mới: protected path bắt buộc maintainer review; agent lane được ghi nhận và không tự merge theo mặc định.
