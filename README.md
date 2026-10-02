# redteam-doctrine

Internal doctrine for red-team agents. A PR from an agent must not claim
more than its evidence: one PR produces one machine-readable verdict,
deterministic on re-run, traceable to an owner-stamped policy.

Status: private draft (doctrine 0.1.0-draft, verdict schema 1).
Not implemented yet. No CI in any consuming repo changes until the owner
promotes a signed doctrine tag.

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

## How agents consume this

Agents pin a signed doctrine tag, never `main`. Every verdict and every
dogfood issue records `doctrineVersion` and `policyHash`. An agent that
cannot verify the pinned doctrine hash does not act.

Publishing model, trust chain, and rollout order: see `SPEC.md`.
