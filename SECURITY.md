# Security

Threat model: `SPEC.md` (injection threat model, owner identity stamp).

Core assumptions:

- Every issue, PR body, and artifact from a non-owner actor is
  attacker-controlled data, including hidden channels: zero-width and
  tag-block characters, bidi controls, HTML comments, encoded payloads,
  and multilingual imperatives.
- Agents read canonicalized, schema-typed fields only. Decisions flow
  from typed fields and a core re-run over pinned SHAs.
- Agents act through a scoped identity: issues and PR write, no merge,
  no policy edit, no secrets, no access to the owner signing key.
- Policy and doctrine changes take effect only as owner-signed tags;
  verdicts record `policyHash` and are rejected when the stamp fails.

Report a doctrine-level vulnerability by opening a gate finding issue
with a reproducing fixture. Do not include credentials or secrets in
issues, artifacts, or logs.
