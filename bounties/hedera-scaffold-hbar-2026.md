# Bounty: Hedera Scaffold-HBAR Template (2026)

Filed: 2026-10-03. Status: intel only. No build started, no registration submitted.
Verdict (build decision): `block` under radar rules until owner stamps otherwise.
Radar kill rules hit: deadline <7d, prize/win <$10k.

## Sources (canonical, token-stripped)

- Landing: https://hedera.com/scaffold-hbar-template-bounty/
- Full brief: https://hedera.com/blog/scaffold-hbar-template-bounty/ (published 2026-09-16, modified 2026-09-29)
- Docs: https://docs.hedera.com/solutions/tools/scaffold-hbar/index
- CLI: `create-scaffold-hbar` npm 0.4.1 (modified 2026-09-28), repo https://github.com/hedera-dev/create-scaffold-hbar
- Harness (optional): https://github.com/hedera-dev/hedera-harness
- Submission form (Google Forms, title "Bounty Submission Form"), linked from landing page.

User-supplied URL carried an `sftoken` JWT. Stripped. Never commit it.

## Facts (each maps to source above)

- Prize: $10,000 pool = 5 x $2,000. Gate-passing templates without a prize still get a Hedera docs listing.
- Deliverable: one public GitHub repo, MIT, original code. Scaffolds in one command:
  `npm create scaffold-hbar@latest -- --template owner/repo`
- Stack: Next.js + Hardhat or Foundry, npm or Yarn workspaces, Node >=20.18.3.
- Layout: monorepo, `packages/` split contracts/frontend, `README.md`, `AGENTS.md`.
- `template.json`: optional in docs, REQUIRED in bounty. Bounty wins.
- >=1 Hedera service in play: HTS, HCS, HSS, or Solidity contract on Hedera.
- >=1 verifiable testnet transaction, evidenced by HashScan or mirror-node link.
- Hedera Harness: recommended, not required, same rubric. If used, submit spec + validators.
- No pull request into scaffold-hbar. CLI fetches external templates via giget from any public repo.

## Timeline (weekdays verified against 2026 calendar)

| Milestone | Date |
|---|---|
| Registration open | Mon 2026-09-14 |
| Build/submissions open | Mon 2026-09-21 |
| AMA/office hours (passed) | Tue 2026-09-29 10:00 ET |
| Submissions close | Sun 2026-10-04 23:59 ET (= 22:59 CDT) |
| Judging | Mon 2026-10-05 to Fri 2026-10-16 |
| Winners | Mon 2026-10-19 |

Filed 2026-10-03 07:35 CDT: ~39h to close.

## Eligibility gate (pass/fail, all required)

| # | Gate item | Evidence artifact |
|---|---|---|
| G1 | Scaffolds clean via `npm create scaffold-hbar@latest -- --template owner/repo` | clean-run log |
| G2 | `template.json` present and valid | file in repo root |
| G3 | `README.md` and `AGENTS.md` present | files in repo root |
| G4 | Install, lint, build pass from fresh scaffold | CI or run log |
| G5 | App boots, core routes return OK | route probe output |
| G6 | >=1 Hedera service + verifiable testnet tx | HashScan/mirror link |
| G7 | No committed secrets, no committed `.env` | secret scan = 0 |
| G8 | MIT licence, original work | LICENSE file |
| G9 | Harness spec + validators, if harness used | `.harness/` artifacts |

## Scoring (panel, 100 pts, gate-passing only)

| Criterion | Pts | Load-bearing test |
|---|---|---|
| Ecosystem integration & value | 35 | Removing the integration breaks the template's point. One-call SDK use scores low. Named examples: SaucerSwap, Lambdaplex, SilkSuite, Chainlink, Supra, Pyth, Axelar, LayerZero, CCIP, lending, decentralised storage. |
| Docs quality | 30 | Unfamiliar dev: scaffold -> running app -> pattern understood, without help. |
| Code quality | 20 | Idiomatic monorepo, meaningful tests, errors handled, no dead code / AI slop. |
| Hedera service depth | 15 | Multiple services composed, or one with real depth. Single token transfer scores low. |

No-testnet-deployment escape hatch (brief): read-only or forked-mainnet integration is acceptable; document it in README.

## Submission form fields (read from the form, 2026-10-03)

Team Details (names, emails, X handles, team size), Mainnet Account ID,
Project Name, Project Description, Project GitHub URL, Video demo, Any other links,
plus a Developer Experience survey.
Unmapped: the brief's HashScan/mirror link and harness spec have no dedicated form
field visible; "Any other links" is the only slot found. Do not assume.

## Contradictions / traps

1. `template.json`: docs say optional, bounty gate says required. Follow bounty.
2. Command syntax differs across Hedera pages (`-- --template` vs `--template`). Gate G1 uses the brief's exact form; verify against CLI 0.4.1 before submitting.
3. Form asks for a Mainnet Account ID; brief demands a testnet transaction. Both can be true (payout vs proof). Reason not stated in sources. Flagged, not guessed.
4. Form includes a Video demo field; the brief's submit list does not mention video. Fill it anyway: form is the submission surface.
5. Brief splits Register (step 1) and Submit (step 4); only one form was found, titled "Bounty Submission Form". A separate registration form is unverified.
6. Built-in templates already cover oracles, bridge, x402, tokenised subscriptions, scheduled payments, cross-chain DCA (`templates/*` branches in hedera-dev/scaffold-hbar, 8 templates per docs). A copy of a built-in scores on integration depth, not novelty of category.
7. Competition is live: `gh search repos "scaffold-hbar template"` returned 30 repos created 2026-09-14 to 2026-10-03. Count is a search snapshot, not an entrant total.
8. Private working repo cannot be submitted: G1 fetches via giget from a public repo. Flip to public + MIT before submitting, or the gate fails mechanically.

## Unmapped claims (no evidence yet, counted not debated)

- Win probability / EV: entrant total unknown.
- Hedera stack ramp for this team: unknown. Radar kill rule: >2d to learn = kill. Deadline leaves ~39h total.
- Testnet account + faucet HBAR: not yet obtained.
- Any specific integration's testnet deployment: unverified per protocol. Verify on mirror node before choosing one.

## Decision needed (owner stamp)

Build or skip. If build: one template, one load-bearing integration verified on
testnet first, docs written to the 30-pt rubric from hour one, G1-G9 run locally
before the form is touched. Registration/submission is an external send: owner sends.

## Outcome (2026-10-03, after owner GO stamp)

Owner stamped GO 2026-10-03 09:03 CDT, overriding the block verdict. Built
`tuannx/scaffold-hbar-milestone-escrow` (USD-priced milestone escrow, Chainlink-gated funding,
optional HCS audit mirror). Key evidence:

- Unit bug caught by on-chain revert: Hedera EVM settles tinybar, JSON-RPC wire is weibar.
  `Underfunded(required=978946962415680850, sent=99852590)`; fixed (quoteHbarTinybar, convert
  x1e10 once at the client wire boundary), commit ac776c9.
- Testnet proof: contract 0x3d2D1E677D272560FF04994098C834d42985e94b (0.0.10843611);
  deploy/create/fund/release HashScan links in the template README and the submission pack.
- True G1: repo flipped public, `npm create scaffold-hbar@latest -- --template
  tuannx/scaffold-hbar-milestone-escrow` scaffolded clean; install/lint/12-of-12 tests/build/
  boot probes all pass; example reuses the live testnet deployment (price 10215058,
  escrowCount 1), no redeploy.
- Submission pack prepared for owner to send (form, DX survey drafted from real friction);
  owner submits before Sun 2026-10-04 23:59 ET. HCS topic creation failed from this VM
  (SDK gRPC DEADLINE_EXCEEDED); module stays fail-soft/unconfigured by design.
