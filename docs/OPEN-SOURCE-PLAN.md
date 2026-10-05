# Open-source plan for redteam-doctrine

Status: plan only. The repo is private; flipping to public is an owner
decision gated by Phase 0. Target license: MIT (matches the surrounding
agent ecosystem: arcade-agent, template repos surveyed).

## Phase 0 — Owner gates (before anything public)

| Gate | Evidence required |
|---|---|
| IP / moonlighting check | Written owner confirmation that this body of work is personal IP, outside employer assignment scope. Nothing ships before this. |
| Secret scan | Full-history scan (`gitleaks`) clean, or history rewritten; report attached to the flip PR |
| License decision | LICENSE file (MIT proposed); README license section synced |
| Name/scope check | Repo description states what doctrine is not (not a framework, not an LLM judge) |

## Phase 1 — Publishable shape

- `LICENSE` (MIT), `CONTRIBUTING.md` already present — add the rule-proposal
  path (3 artifacts) to it; `SECURITY.md` already present — add disclosure
  timeline; `CODE_OF_CONDUCT.md` (Contributor Covenant).
- Mark repo as a **GitHub template**; add `docs/ADOPT.md`: copy DOCTRINE.md +
  `schema/` + `policy/` + `skills/pr-redteam` into a target repo, pin the
  doctrine tag in `.redteam/policy.json`, run the gate locally, then CI.
  Modeled on the adoption flow of codex-agent-coordination (review-first,
  CI-second).
- Versioning: `VERSION` (doctrine) + `schema` counter already exist; tag
  `doctrine-0.1.0` at flip; policy pin examples use the tag, never `main`.
- Public fixtures: planted-bad/clean PR pairs under `fixtures/` runnable
  offline, so anyone can reproduce a BLOCK and a PASS in < 60s.

## Phase 2 — Interoperability adapters (the field's missing layer)

- **MCP server** exposing `run_gate(base, head, policy) -> verdict.json` and
  `explain_verdict(verdict) -> evidence map`. Verdicts stay deterministic;
  the LLM only transports them. (ArcadeAttest's MCP tools are the pilot.)
- **PR comment renderer** (exists) packaged as a reusable GitHub Action:
  `uses: tuannx/redteam-doctrine@v1` with pinned policy; comment rendered
  from verdict JSON by template, no generated prose.
- **AGENTS.md bridge**: a short section template other repos paste, pointing
  agents at the pinned doctrine ("name is contract…" summary + gate command).
- Optional A2A Agent Card once identity work (signed cards) is exercised by
  ArcadeAttest attestations.

## Phase 3 — Community and proof

- Public dogfood: arcade-agent-examples runs the gate on every PR; results
  posted as checks, history public. This is the leaderboard-equivalent:
  reproducible, not self-graded.
- Contribution ladder: rule proposals need the 3 artifacts (bad case, clean
  case, measured runtime); issues stay schema-typed (existing templates).
- Release cadence: doctrine changes only via learning-loop distillation
  PRs (docs/LEARNING-LOOP.md); each release notes which merged PRs changed
  which instruction.
- Docs: README keeps the law in the first screen; `docs/COMPARISON.md`
  states the position vs frameworks/templates honestly, gaps included.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Public issues become a prompt-injection vector | Charter already treats issues as attacker-controlled data; templates enforce structured fields; agents never fetch URLs from issues |
| Users treat WARN as PASS | Verdict schema documents enforcement modes (advisory vs blocking); Action defaults to blocking on BLOCK only, stated loudly |
| Doctrine rots into a big prompt | Learning loop requires evidence per instruction; distillation PRs must delete or amend stale lines, not only append ("less code wins" applies to instructions too) |
| Employer IP ambiguity | Phase 0 gate: no flip without the owner's written confirmation |

## Sequencing (owner-time estimates)

- Phase 0: one owner session (~30 min) — IP check + license pick + scan run.
- Phase 1: one agent sprint (~half day) — packaging + fixtures + ADOPT.md,
  delivered as a PR for owner review (doctrine repo: owner merges).
- Phase 2: two sprints — MCP server, then the Action; each dogfooded on
  arcade-agent-examples before announcement.
- Phase 3: ongoing; first public dogfood results before any launch post.
