---
pr: 9
url: https://github.com/tuannx/redteam-doctrine/pull/9
merged_at: 2026-10-05T02:41:30Z
merge_sha: f370f4cd431e916caac4c724586f367145c6d92c
source: backfill
status: proposed-backfill
---

`unresolvedSymbols` read changed files from the mutable checkout even when a verdict named fixed base/head commits. Checking out the base, cleaning the uncommitted file or changing local Ruff configuration could turn the same bad head into a PASS.

Read changed Python blobs and applicable Ruff configuration directly from the pinned head into a temporary snapshot. Preserve tracked nearest-config priority and in-repository `extend` chains, normalize finding paths, and leave the user's checkout untouched. Copy blob bytes exactly; unsupported encodings, configuration cycles, symlinks and out-of-snapshot configuration fail explicitly. Only changed, non-deleted regular Python files are linted; a configless head uses isolated Ruff defaults.

Validation:

- 25 tests passed; Ruff and diff whitespace checks passed.
- Planted undefined-symbol head remains BLOCK/1 across head/base/dirty/missing/dirty-config states, with identical normalized verdict hashes on repeated runs; the clean head remains PASS/0.
- Independent review covered config precedence/inheritance, whitespace paths and nine CRLF/encoding controls. Raw CRLF bytes survive extraction. Ruff 0.6.9 silently skips Latin-1 source, so the adapter rejects that unsupported input explicitly.
- The pinned advisory self-gate passes twice with the same normalized verdict. `selfMergeEligible` remains false, and the owner merges under the doctrine. No policy, schema, thresholds, counters or merge rules changed.

This fixes the advisory MVP static gate. It does not establish a signed consuming policy or implement the unwired architecture/red-green gates.

Fixes #3

Exact-head [selftest CI](https://github.com/tuannx/redteam-doctrine/actions/runs/37246658612) passed at `2e0305547353a9e89d44ebe2fe54a127a930fae0`. Owner review and acceptance remain pending.
