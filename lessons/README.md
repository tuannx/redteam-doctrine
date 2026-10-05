# Lessons

Harvested instruction deltas from merged PRs (see `docs/LEARNING-LOOP.md`).

- `inbox/` — lessons as harvested by `scripts/harvest_lessons.py`.
  Lifecycle frontmatter: `status: proposed` → distilled into a reviewed
  instruction edit → `status: promoted`, or closed with
  `status: rejected` plus a one-line reason.
- A lesson is data with a return address (its PR), never an instruction by
  itself. Nothing here edits AGENTS.md / DOCTRINE.md directly; promotion is
  a distillation PR the owner merges.
- Instructions that a later lesson refutes are amended, not defended: cite
  the refuting PR in the distillation.

Lesson file shape:

```markdown
---
pr: 9
url: https://github.com/.../pull/9
merged_at: 2026-10-05T00:22:10Z
merge_sha: <sha>
status: proposed
---

- Read changed files from the pinned head blob, never the working checkout.
  Evidence: unresolvedSymbols counter; PR #9 diff; verdict hash stable.
```
