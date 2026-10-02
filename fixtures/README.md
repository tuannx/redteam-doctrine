# Fixtures

Claims are verified against fixtures, not prose. Layout when populated:

- `prs/clean-*` — change sets that must produce `pass`.
- `prs/planted-<gate>-*` — change sets that must produce `block` at the
  named gate (invented symbol, new smell, secret, unmapped claim,
  hollow test, flaky ordering).
- `issues/injection-*` — issue bodies carrying hidden payloads
  (zero-width, HTML comment, foreign-language imperative, base64). Each
  must yield a verdict identical to its clean twin, with a quarantine
  report listing the removed spans.
- `golden/` — expected `verdict.json` per fixture, compared byte-for-byte
  after normalization.

A fixture enters the corpus through a rule-proposal issue with its
expected verdict attached. Nothing here is trusted until the gate
reproduces the golden file.
