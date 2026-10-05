# Maintainer patterns mined from arcade-agent/arcade-agent (spike)

Date: 2026-10-04. Corpus (via `scripts/fetch_review_corpus.py`, deterministic
stage 1): 33 merged PRs (lemduc 19, tuannx 14), 44 inline review comments
(7 human), 5 human reviews with bodies. Spike-sized corpus — patterns below
are the *practiced* review culture of the two maintainers, quoted, not
inferred statistics. Bots (Copilot 35 comments) excluded deliberately.

## Patterns with evidence

1. **Determinism is verified by the maintainer's own re-run, not by claim.**
   lemduc, CHANGES_REQUESTED on PR #19: "determinism is proven safe — I parsed
   the identical tree with main's code and this branch's code and got
   byte-identical [output]". Gate mapping: already mechanical in
   redteam-doctrine (double-run verdict hash). Candidate rule: reviews that
   assert determinism must attach the two run hashes.

2. **Fixtures assert exactly; smoke tests earn requests for changes.**
   PR #19: "the Maven dual-root fixture with exact FQN/edge assertions is
   exactly right". PR #17 praises "contract conformance is essentially
   perfect (registration, `.kt`/`.kts`, every dispatch surface wired)".
   Gate mapping: doctrine's planted-bad/clean pair requirement is the same
   instinct, formalized.

3. **New surfaces must mirror the established architecture.**
   PR #17: "mirrors the Java parser's two-pass design faithfully". PR #16:
   premise checked against the dependency's source (`FuncMetadata...` in
   mcp 1.28.1) before accepting the design. Not mechanically checkable
   today; a distillation candidate for AGENTS.md guidance, not a gate.

4. **Author replies close the loop with SHA + test name — never prose.**
   tuannx, PR #18/#19 (5 comments, same shape): "Fixed in 55d9760. ...
   Covered by the invalid-manifest regression test." / "Covered by
   test_ingest_rejects_unknown_language". This is the doctrine's
   claim→evidence rule already in practice upstream.

5. **Silent failure is the unforgivable sin.**
   tuannx, PR #6: "Token budget is silently ignored here." + requests an
   e2e test in CI. Doctrine mapping: coverage warnings + "no silent
   unknowns" (ArcadeAttest issue #3 fix is the same pattern).

6. **Docs ship with the metric.**
   lemduc approving PR #5: "Just need to update the readme about the new
   metric". Merged history agrees: #23/#24/#37 are docs-truth fix PRs.
   Gate mapping: README anchor sync (done by hand in nexus-crm; candidate
   for a mechanical counter).

## What mining at this scale can and cannot do

- 12 human review artifacts is enough to name a culture, not to train a
  judge. Any pattern promoted to a *gate* still needs the doctrine's three
  artifacts (planted-bad, clean, measured runtime) — mining proposes,
  gates dispose.
- The richest signal was not comment volume but *review structure*:
  what the maintainer re-ran himself (determinism), what he read in the
  dependency source (premise), what he demanded exactly (fixtures).
  A production miner should extract review *actions*, not just text.
