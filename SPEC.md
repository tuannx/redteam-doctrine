# Red-Team Tools Spec — PR Hallucination Gates for arcade-agent

Saved: 2026-10-02. Self-reviewed and deduplicated: 2026-10-02.
Status: Spec only. Not implemented, no CI changed.

## Intent

One PR produces one machine-readable verdict. Every claim maps to evidence,
every check is deterministic, and the fastest checks run first. No LLM judge
at any gate.

Law: name is contract, text is evidence, everything else is noise.

LLM role, the only one: extract claims from PR prose. Every extracted claim
is verified by a deterministic matcher. Uncertain extraction becomes explicit
missing evidence, never an automatic pass.

## Tool selection gates

A tool enters the stack only if it passes all five gates. Fail one, excluded.

- G1 DeterministicOutput: same input produces same JSON or SARIF output.
- G2 DiffAware: runs on changed files or changed lines, not the whole repo by default.
- G3 PinnedAndOffline: version pinned in repo config, no network at gate time.
- G4 ConfigSuppression: false positives are disabled by repo config, never by prose.
- G5 SingleOwnerPerCategory: no two selected tools own the same category.

Ranking after gates: evidence strength divided by runtime seconds per PR.

## Core stack by attack category

### OrchestrationAndEvidence (reuse only)

- `git` and `gh` inside the existing arcade-agent arch-drift GitHub Action.
  No new CI system.
- `pr_redteam` — the only new glue code. Responsibilities named by contract:
  `collectDiffScope`, `runStaticGates`, `evaluateArchitecturePredicates`,
  `verifyRedGreenTests`, `hashNormalizedVerdict`, `renderPrCommentFromVerdict`.
- `jq` and `check-jsonschema` validate `verdict.json` before any comment renders.
- PR comment is rendered from `verdict.json` by template. No generated prose.

### NecessityAttack — less code is better

- `git diff --numstat -z` produces `netLocChanged`, `filesTouched`
  (machine form only; see DOCTRINE.md principle 10).
- `scc` counts lines by language excluding tests and generated files.
- `vulture` (Python) and `knip` (TypeScript) produce dead code and unused
  export candidates.

Primary counters: `netLocChanged`, `filesTouched`, `deadCodeCandidates`,
`newDependencies`, `newPublicSymbols`.

Rule: every added line must be correctly named, covered by a test, or deleted.

### InventedSymbolAttack

- `ruff` — undefined names, unused imports, naming rules. Millisecond tier.
- `ast-grep` with tree-sitter, reusing the parser family arcade-agent already
  depends on. Structural patterns only, no regex guessing, no LLM review.
- `pyright` (Python) or `tsc --noEmit` (TypeScript) on changed files only,
  in the deep tier because they cost more seconds per evidence unit.

Primary counter: `unresolvedSymbols`. Gate target: 0.

### ArchitectureAttack — arcade-agent audits itself

- Existing arcade-agent tools, zero new analysis code:
  `changelog_architecture`, `detect_smells`, `compute_metrics`.
- Decision predicates (MVP set from the Decision API design):
  `no_new_smells`, `max_responsibility_shifts`, `component_entity_cap`.
- `import-linter` (Python) or `dependency-cruiser` (TypeScript) enforces
  hexagonal layer contracts. Domain importing an adapter is an immediate fail.

Primary counters: `newSmells`, `responsibilityShifts`,
`largestComponentEntities`, `layerContractViolations`.

### TestTruthAttack

- `pytest -n auto` against two git worktrees: base must be red for new tests,
  head must be green. A test green on both sides proves nothing.
- `diff-cover` produces `changedLinesCoveredPercent` for the diff only.
- Double-run determinism check per the Determinism contract below.
- `mutmut` only in the deep tier, sampled on changed functions, timeboxed,
  advisory and never blocking.

Primary fields: `tests.redOnBase`, `tests.greenOnHead`,
`changedLinesCoveredPercent`, `nondeterministicDiffLines`,
`mutationSurvivorsSampled`.

### ProseAndSecretAttack

- Claim matcher (part of `pr_redteam`): extracts every number and completion
  claim from the PR description and changed markdown, then matches each one
  against a field in the run artifacts. Unmatched claims are counted, not debated.
- Comment redundancy checker: a comment whose tokens restate the following
  code line is counted as redundant. Comments survive only for constraints
  outside the code (parser blind spots, upstream bug links).
- `gitleaks` scans diff and logs for secrets before any artifact is published.

Primary counters: `unmappedClaims`, `redundantCommentLines`, `secretsFound`.
Gate targets: 0, 0, 0.

## verdict.json — the contract

```json
{
  "schemaVersion": 1,
  "pr": {"baseSha": "...", "headSha": "..."},
  "policy": {"policyVersion": 1, "policyHash": "...", "coreVersion": "..."},
  "actor": {"app": "...", "runId": "..."},
  "attestation": "...",
  "counters": {
    "netLocChanged": 0,
    "filesTouched": 0,
    "deadCodeCandidates": 0,
    "newDependencies": 0,
    "newPublicSymbols": 0,
    "unresolvedSymbols": 0,
    "newSmells": 0,
    "responsibilityShifts": 0,
    "largestComponentEntities": 0,
    "layerContractViolations": 0,
    "unmappedClaims": 0,
    "redundantCommentLines": 0,
    "secretsFound": 0,
    "nondeterministicDiffLines": 0,
    "hiddenSpansRemoved": 0,
    "encodedPayloadsFound": 0,
    "nonOwnerCommandAttempts": 0
  },
  "tests": {
    "redOnBase": true,
    "greenOnHead": true,
    "changedLinesCoveredPercent": 0,
    "mutationSurvivorsSampled": 0
  },
  "verdict": "pass | warn | block",
  "findings": [
    {"gate": "unresolvedSymbols", "file": "path.py", "line": 1, "evidence": "..."}
  ]
}
```

Field names are the contract. Any new counter or field enters this schema
by name before any code emits it.

## Run profiles and performance budgets

- PR-Fast (blocking, budget 60s total): diff scope and secret scan under
  5s combined; static gates (ruff, ast-grep, predicates) under 30s on a
  typical PR; then diff-cover and the double-run hash. No LLM, no
  exception path.
- PR-Deep (advisory or nightly): adds pyright or tsc on the full change
  surface, sampled mutation, semgrep with a ruleset pinned in the repo.
- Release-Gate (blocking for release): full test suite on base and head,
  full double-run of the whole pipeline, Decision API verdict with
  thresholds derived from recorded history, not invented per release.

Any gate that cannot meet its budget moves to PR-Deep automatically;
it does not slow the blocking path.

## Determinism contract

- Inputs pinned: base SHA, head SHA, tool versions, ruleset versions.
- Environment locked: `PYTHONHASHSEED=0`, `TZ=UTC`, `LC_ALL=C`,
  `SOURCE_DATE_EPOCH` from the head commit timestamp.
- Outputs normalized: sorted keys, stable ordering, durations isolated
  in fields excluded from verdict hashing.
- Acceptance: run PR-Fast twice on the same PR; the two verdict hashes
  must be identical.

## Distribution — one Decision Core, three adapters

The core owns predicates, counters, and the `verdict.json` schema.
Adapters never invent decision logic.

- GitHub Action adapter: blocking PR gate. Renders the PR comment from
  `verdict.json` by template, sets check status `pass | warn | block`.
- Agent Skill adapter: the agent runs the same gate locally before opening
  a PR, reads findings from `verdict.json`, and fixes them. The skill
  explains evidence only; it never judges.
- HTTP Decision API adapter (v0.2, optional): a thin Worker or FastAPI
  facade over the same core for external callers. Actions and skills call
  the core locally or over HTTP; either way the verdict schema and hash
  are identical.

Positioning: a PR from an agent must not claim more than its evidence.

## Owner identity stamp — trust the right person

The red team trusts exactly one identity: the product owner. The stamp is
cryptographic and procedural, never a name typed in prose.

Trust chain:

```text
owner signing key
  -> signed policy release (tag)
  -> GitHub Action runs pinned core under policyHash (OIDC-attested run)
  -> verdict.json hash + attestation
  -> Skill verifies policyHash and attestation before explaining findings
```

Mechanisms:

- Owner root of trust: the GitHub account or org owner. `CODEOWNERS` assigns
  `.redteam/`, `.github/workflows/`, and the verdict schema to the owner.
- Protected paths: a ruleset requires PR review by the owner for those
  paths, requires signed commits, and grants no bypass to bots or apps.
  Agents hold a scoped GitHub App identity (issues and PR write, no merge,
  no policy edit); every verdict records its actor (app, run ID).
- Policy as the stamped artifact: `.redteam/policy.json` plus baselines live
  under owner-only paths. A policy change increments `policyVersion` and
  only counts when released as a signed annotated tag (owner SSH signing
  key registered on GitHub). `verdict.json` records `policyHash`; a verdict
  is valid only under a stamped policy.
- Run attestation: the Action uses GitHub OIDC to attest the verdict
  artifact (build provenance), binding the `verdict.json` hash to
  repository, workflow, and commit. The skill verifies the policy tag
  signature and that the verdict `policyHash` matches before trusting or
  explaining it.
- Signing sits outside the determinism contract: the verdict hash is
  computed over normalized JSON first, then signed. Tampering with policy
  or verdict after the fact breaks the signature, never rewrites history.

Acceptance checks for the stamp itself:

- Modify `policy.json` without an owner-signed release tag: the Action
  blocks with a `policyStamp` finding.
- An agent PR touching `.redteam/policy.json` cannot merge without owner
  review; an unsigned commit on a protected path shows unverified and fails
  the ruleset.
- A forged or stale `verdict.json` (wrong `policyHash`, missing attestation)
  is rejected by the skill before any finding is explained.

## Injection threat model

Assume every issue is attacker-controlled data. The worst class is the
hidden channel: content invisible to the human owner but fully readable
by an agent tokenizer.

Attack surface:

- Invisible characters: zero-width space and joiners, the Unicode Tag
  block, bidi controls that reorder display, private-use codepoints,
  homoglyph substitution across scripts.
- Markup channels: HTML comments, image alt text, link text that differs
  from its destination, hidden elements.
- Encoded payloads: base64, hex, or ROT13 inside code blocks that read as
  inert code to a human and decode into instructions for an agent.
- Multilingual payloads: imperatives written in a language outside the
  owner's scanning habits, or mixed scripts that evade keyword filters.

Defense order: structural immunity first, detection second. Keyword
detection never keeps up with new encodings, so the gate must stay safe
even when detection misses.

1. Canonical view. Agents never read a raw issue. A deterministic
   sanitizer (not an LLM) runs first: NFKC normalization, removal of
   dangerous format controls (zero-width, bidi, tag block), markdown
   rendered down to visible text, HTML comments stripped. Removed spans
   are not silently dropped; they enter a quarantine report the owner
   sees, with count, position, and category. What the agent reads is
   exactly what the owner can inspect, and hidden attempts become
   visible findings. Normalization strips only control and tag classes;
   legitimate combining marks (for example Vietnamese diacritics) are
   preserved.
2. Encoded payloads are structurally inert. Code blocks are data and are
   never executed. Long base64 or hex strings are counted in
   `encodedPayloadsFound`; decoding, if done at all, happens in a sandbox
   for classification only, and the decoded text never re-enters as
   instruction.
3. Schema-only decisions. Even a payload that reaches an LLM cannot
   change behavior: decisions flow only from typed schema fields and a
   core re-run over pinned base and head SHAs. Issue prose maps to no
   action, in any language.
4. Owner-only command channel. Labels and commands take effect only when
   the actor is the owner; attempts by anyone else increment
   `nonOwnerCommandAttempts`. Commands inside an issue body are ignored.
5. No issue-driven egress. Agents never fetch URLs from an issue and never
   install anything an issue suggests; the toolset stays pinned and
   offline (gate G3).
6. Locked output. Agent comments render from `verdict.json` by template;
   no issue content can phrase an approval or a merge.

Quarantine rule: when `hiddenSpansRemoved` is above zero, the issue is
quarantined as `needs-evidence` and cannot serve as evidence for any gate.

Acceptance fixtures: four planted issues — zero-width payload, HTML
comment payload, foreign-language imperative, base64 payload — must each
produce a verdict identical to the clean issue, with a quarantine report
listing exactly the spans removed.

## Dogfooding through GitHub Issues

Issues are evidence objects, not discussion threads.

- Every dogfood issue must carry: the `verdict.json` artifact, base and
  head SHA, gate name, `file:line`, expected versus actual counter, one
  repro command, and pinned tool versions. Missing fields, or a
  quarantined issue (threat model above), earn the `needs-evidence`
  label; prose-only claims are not reviewed.
- An agent proposes a new gate or rule with three artifacts: a planted bad
  PR that must block, a clean PR that must pass, and measured runtime in
  seconds. Fewer than three artifacts means no code is written.
- Self-hosting: a PR that adds a rule must itself pass `pr_redteam`.
  False positives are fixed by config PRs with regression fixtures, never
  by comment debate.
- Dedupe by finding hash: the same hash comments on the existing issue
  instead of opening a new one.
- Agent permissions: open issues, attach evidence, propose rules, submit
  PRs. Agents never merge, never lower thresholds, never suppress by prose.
  Threshold changes come from a script over recorded history. The owner
  merges; the merge is the acceptance.

MVP dogfood target: `arcade-agent-examples` (deterministic scenarios already
exist). PR-Fast runs advisory for one week, then zero-tolerance counters
block: `unresolvedSymbols`, `secretsFound`, `unmappedClaims`, `newSmells`.
Milestone: the first five dogfood issues all carry a valid `verdict.json`,
and the gate blocks a planted-bad-PR fixture.

## Goal

MVP success criteria, each measurable against the sections above:

- 100 percent of PRs carry a schema-valid `verdict.json`.
- Two runs on the same SHA pair produce the same normalized hash
  (Determinism contract).
- PR-Fast p95 stays under the 60s budget on the dogfood repo.
- A planted-bad-PR fixture is blocked; a clean fixture passes.
- Injection fixture issues never change the verdict (threat model).
- Every verdict traces to an owner-stamped policy (`policyHash`).

Non-goals: no dashboard, no SaaS, no new CI platform,
no second tool per category, no unpinned ruleset from the network.

## Test plan

The suite runs the acceptance checks defined in each section as one
fixture matrix, comparing full verdicts against golden files:

- One planted PR per attack category with its expected verdict: clean
  pass; invented symbol block; new smell block; secret block; unmapped
  claim block; hollow test (green on base and head) fail; flaky ordering
  producing `nondeterministicDiffLines` above zero.
- Red-green truth and the determinism double-run, as defined in
  TestTruthAttack and the Determinism contract.
- The four injection fixtures and the stamp acceptance checks, as
  defined in their sections.
- A canonicalization regression test: legitimate combining marks
  (Vietnamese diacritics) survive the sanitizer.
- Performance: any gate that misses its budget on fixtures is demoted
  from PR-Fast to PR-Deep automatically (Run profiles).

## Publish manifest (v0.1)

- GitHub Action: the blocking PR gate; verdict artifact plus check
  status as outputs.
- CLI `pr_redteam` and JSON Schema: the shared Decision Core with
  `run`, `verify`, and `render` commands; schema file versioned with
  `schemaVersion`.
- Skill pack: `SKILL.md` files for running the gate locally before
  opening a PR and for contributing through evidence-based issues.
- Sample policy: `.redteam/policy.json`, pinned rulesets (ruff,
  ast-grep, gitleaks, import-linter or dependency-cruiser),
  `CODEOWNERS`, and a guide for rulesets and signed release tags.
- Public fixture corpus: planted bad PRs, clean PRs, injection issues,
  and golden verdicts, so anyone can verify the claims.
- Docs: determinism contract, injection threat model, owner-stamp
  guide, verdict schema reference.
- Release identity: owner-signed tag and build attestation for the
  release artifacts; changelog keyed to `schemaVersion`.

The HTTP Decision API facade is v0.2, optional, over the same core,
only after the Action and Skill have completed dogfooding.

## Rollout order (each step measurable)

1. `collectDiffScope` plus counters only, advisory mode. Done when every PR
   in one week carries a valid `verdict.json`.
2. Blocking gates at zero-tolerance counters: `unresolvedSymbols`,
   `secretsFound`, `unmappedClaims`, `newSmells`. Done when a synthetic PR
   with a planted invented symbol is blocked.
3. Red-green test verification and double-run hash. Done when a planted
   flaky ordering change produces `nondeterministicDiffLines > 0`.
4. Thresholds for `netLocChanged` and `responsibilityShifts` derived from
   recorded PR history. Done when thresholds are computed by script from
   the history file, not written by hand.

## Self-dogfood review log

2026-10-02: this spec was reviewed by its own rules. Findings, all fixed
in this pass:

- Duplicated rules merged to one canonical home each: the no-LLM-judge
  law (Intent), the double-run (Determinism contract), red-green truth
  (TestTruthAttack), the 60s budget (Run profiles), self-hosting
  (Dogfooding), and the injection and stamp acceptance checks (their own
  sections). Goal and Test plan now reference those homes instead of
  restating them.
- Schema drift fixed: the `verdict.json` sketch predated five fields
  (`policyVersion`, `policyHash`, `coreVersion`, `actor`, `attestation`)
  and five counters (`newPublicSymbols`, `largestComponentEntities`,
  `hiddenSpansRemoved`, `encodedPayloadsFound`,
  `nonOwnerCommandAttempts`) that later sections already required; all
  are now in the schema, per the rule that fields enter the schema
  before code emits them. Test field naming unified as
  `tests.redOnBase` and `tests.greenOnHead`.
- `needs-evidence` had two triggers in two sections; both are now named
  in one place (Dogfooding, with the quarantine rule in the threat
  model).
