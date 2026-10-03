# redteam-doctrine

Internal doctrine for red-team agents. A PR from an agent must not claim
more than its evidence: one PR produces one machine-readable verdict,
deterministic on re-run, traceable to an owner-stamped policy.

Status: private draft (doctrine 0.1.0-draft, verdict schema 1).
MVP step 1 is implemented on branch `mvp/pr-redteam-step1`: diff
counters, ruff F821, secret patterns, schema-valid `verdict.json`,
normalized hash, comment renderer. Architecture predicates and
red-green verification are step 2. No consuming repo's CI changes
until the owner promotes a signed doctrine tag.

## Layout

- `DOCTRINE.md` — the charter every red-team agent acts under.
- `SPEC.md` — the full tool-stack spec (gates, counters, profiles,
  determinism contract, threat model, publish manifest).
- `schema/verdict.schema.json` — the verdict contract. Field names enter
  here before any code emits them.
- `policy/policy.example.json` — per-repo policy shape. Each consuming
  repo keeps its own stamped copy under `.redteam/`.
- `fixtures/` — planted bad PRs, clean PRs, injection issues, golden
  verdicts. Claims are verified against these, not against prose.
- `.github/ISSUE_TEMPLATE/` — evidence-first issue forms for dogfooding.
- `pr_redteam/` — the gate CLI (`run`, `verify`, `render`). MVP scope is
  stated in `pr_redteam/core.py`; unwired counters read 0 = not run.
- `tests/` — fixture tests: clean pass, planted invented symbol, planted
  secret, double-run hash.
- `skills/pr-redteam/` — the agent skill for running the gate locally
  and contributing through evidence-based issues.

## How agents consume this

Agents pin a signed doctrine tag, never `main`. Every verdict and every
dogfood issue records `doctrineVersion` and `policyHash`. An agent that
cannot verify the pinned doctrine hash does not act.

## G-A-E alignment (2026-10-02)

The doctrine is aligned to the three highest-scored decision families:
G AI-Generated Code Gate, A PR & CI Merge Gate, E Monorepo & OSS
Maintainer. One Decision Core, three lanes (agent / pr / maintainer),
one verdict schema. Agent lane treats WARN as BLOCK; maintainer lane
only surfaces WARN/BLOCK and protected-path hits. See
`ALIGNMENT-GAE.md` for the 30-case map, triage weights, and rollout.

Policy profiles: `policy/policy.agent.json`, `policy/policy.pr.json`,
`policy/policy.maintainer.json`.

Publishing model, trust chain, and rollout order: see `SPEC.md`.
