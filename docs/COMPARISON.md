# Doctrine vs the 2026 agent-operating field — comparison

Date: 2026-10-04. Sources: field survey of AGENTS.md adoption, template repos,
orchestration frameworks, agent eval benchmarks, and governance writing
(cited in the research notes; every claim below maps to a mechanism in this
repo or is marked as a gap).

## What the field converged on (2026)

1. **Repo contract files.** AGENTS.md is the cross-vendor convention
   (60k+ open-source projects, nested per-subtree), usually paired with
   `.agents/skills/` loaded on demand. Templates (romanroff/template-repo,
   ikairoseki/codex-agent-coordination, d-oit/do-web-ui-template-2026)
   package: AGENTS.md + skills + deterministic local gates + PR-review-first,
   CI-second adoption.
2. **Orchestration frameworks.** LangGraph (state machines, best
   observability), CrewAI (role crews, fastest MVP), AutoGen in maintenance
   mode. They orchestrate; they do not govern.
3. **Evaluation is leaving unit tests behind.** SWE-Serve rejects ~1/3 of
   patches that pass other evals; SWE-Milestone (ICML 2026) grades continuous
   repo evolution, not single issues.
4. **Governance consensus.** "Governance lives in deterministic code, not
   stochastic prompts." Protocols (MCP for tools, A2A for agent-to-agent)
   consolidated under the Linux Foundation's Agentic AI Foundation; the open
   frontier is agent identity — attributable, revocable, per-agent.

## Where this doctrine is stronger

| Axis | Field default | redteam-doctrine |
|---|---|---|
| Review output | Prose comments; LLM judge common | One machine-readable `verdict.json` (`pass \| warn \| block`), no LLM judge anywhere (DOCTRINE.md §1) |
| Claim accountability | Gates check code, not claims | Every PR claim maps to evidence; unmapped claims are counted in the verdict (`unmappedClaims`) |
| Determinism | "Run tests twice if you like" | Pinned SHAs, blob-read snapshots, normalized output, verdict hash stable across runs (PR #9 closes the mutable-checkout hole) |
| Untrusted input model | Rarely modeled | Issues are attacker-controlled data; only schema-typed fields map to actions (DOCTRINE.md §8) |
| Trust root | Human sign-off checkboxes | One identity: the owner. Owner merge **is** the acceptance; policy is a signed tag |
| Self-application | Templates demo on toy repos | Dogfood is a gate, not a slogan: the doctrine runs on its own PRs and on arcade-agent-examples |
| Rule changes | Edit a prompt, hope | New rules need 3 artifacts: planted-bad PR, clean PR, measured runtime (issue template `rule-proposal.yml`) |

## Where the field is ahead (honest gaps)

1. **Onboarding/packaging.** Template repos ship "use this template" flows,
   adopt scripts, and migration guides. Doctrine today is a repo you must
   already understand. → OPEN-SOURCE-PLAN.md P1.
2. **Skill packaging.** Field skills are portable, lifecycle-managed
   (discover → create → test → govern → retire). Doctrine has one skill
   (`skills/pr-redteam`); no versioning or eval sets yet.
3. **Observability surface.** LangSmith-style traces, dashboards, and cost
   telemetry are table stakes elsewhere; doctrine emits verdict JSON and
   stops. Deliberate (less code wins) but it caps adoption.
4. **Ecosystem adapters.** No MCP server, no A2A Agent Card, no LangGraph /
   CrewAI bindings. The verdict engine is portable; the adapters are missing.
5. **Public proof.** Benchmarks publish leaderboards. Doctrine's evidence is
   private-repo dogfood runs; open source needs public fixtures and runs.

## Position statement

Frameworks decide *how agents move*. Templates decide *how repos look*.
This doctrine decides *what may be believed* — which claims about a change
are backed by evidence, reproducibly. That is the layer the 2026 field is
missing, and the layer agent identity/attestation work (A2A signed cards,
EAS-anchored verdicts) is starting to demand.
