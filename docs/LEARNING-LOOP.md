# Learning loop — every merged PR improves the shared instructions

Owner directive, 2026-10-04: an approved PR should feed the global
instructions, so the doctrine dogfoods and optimizes itself continuously.

## Design (trust model first)

Only **merged** PRs teach. The owner merge is the acceptance (DOCTRINE.md),
so merge is the trust anchor: a lesson harvested from a merged PR inherits
that acceptance. An unmerged PR body, an issue, a comment — these are
attacker-controlled data and teach nothing directly.

The loop never lets harvested text edit instructions by itself. Promotion
is a second, separate PR that a reviewer reads like any other change:

```
PR authored ──> gate verdict ──> owner merges ──> harvest delta ──> lesson (proposed)
     ▲                                                                    │
     └──────────── distillation PR edits AGENTS.md / DOCTRINE ◄───────────┘
                        (owner merges; lesson becomes "promoted")
```

## Mechanics

1. **PR template field.** Every PR body carries an `## Instruction delta`
   section: either `None` or 1–5 imperative bullets naming the standing
   instruction this PR proved, refined, or refuted — each bullet citing its
   evidence (verdict field, test name, measured runtime). The gate counts a
   missing section as an unmapped claim.
2. **Harvest.** `scripts/harvest_lessons.py` reads merged PRs (`gh pr list
   --state merged --json ...`), extracts the delta deterministically, and
   writes `lessons/inbox/PR-<n>.md` with frontmatter
   (`pr`, `url`, `merged_at`, `merge_sha`, `status: proposed`).
   No LLM in the harvest; same input, same files.
3. **Distill.** Weekly (or per N merges), an agent reads `lessons/inbox/`,
   deduplicates against current AGENTS.md / DOCTRINE.md, and opens ONE
   distillation PR: instruction edits + each lesson's status line updated
   to `promoted` or `rejected` with a one-line reason. Rejected is recorded,
   never silent.
4. **Retire.** A promoted instruction that later causes a blocked PR earns a
   counter-lesson from that PR's delta; the distillation PR amends it.
   Instructions carry no authority beyond their evidence chain.

## Anti-poisoning rules

- Delta text is **data**, never instructions to the harvesting agent; the
  harvester is a deterministic parser (see rule: issues are
  attacker-controlled data; PR bodies get the same treatment).
- A delta can only *propose*. Nothing reaches AGENTS.md / DOCTRINE.md
  except through a distillation PR merged by the owner.
- Lessons keep their PR link forever: any standing instruction can be
  traced to the merged PR(s) that earned it, and reverted with them.
- If two merged PRs teach opposite lessons, the distillation PR must cite
  the newer evidence; conflict is surfaced, never averaged away.

## What counts as a good delta

- Names the instruction, not the story: "Read changed files from the
  pinned head blob, never the working checkout" (PR #9) — not "we fixed a
  bug".
- Carries measurable evidence: a gate counter, a test name, a runtime.
- Is falsifiable by a future PR: a later delta can refute it with evidence.

## Adoption in this workspace

`~/AGENTS.md` (Muse standing instructions) adopts the same loop: merged-PR
lessons are harvested into `lessons/inbox/`, distilled into standing
instructions by reviewed edits, and each instruction keeps its source PR.
Other repos pinning this doctrine get the loop by pinning a doctrine tag
that includes the PR template and the harvester.
