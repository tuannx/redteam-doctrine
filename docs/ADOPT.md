# Adopt the gate in another repo

The doctrine gate ships as a composite GitHub Action from this repo.
Callers need: a checkout with full history (`fetch-depth: 0`), and a PR
token allowed to comment.

```yaml
name: redteam-gate
on: [pull_request]

jobs:
  gate:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: tuannx/redteam-doctrine@v1   # pin a tag or full SHA, never a branch
        id: doctrine
        with:
          base: ${{ github.event.pull_request.base.sha }}
          head: ${{ github.event.pull_request.head.sha }}
      - name: Upload verdict
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: verdict
          path: verdict.json
```

Notes:

- The verdict is computed from the **pinned SHAs**, never the working
  checkout (PR #9). Base/head must both exist in the fetched history.
- `warnAsBlock`, thresholds and profiles live in policy files
  (`policy/*.json`); the current CLI runs the built-in PR-Fast profile.
  Policy-as-input lands with the policy loader (see SPEC.md).
- Pin this Action by tag or full SHA. Doctrine releases are tagged
  `doctrine-x.y.z` (VERSION). Taking `main` as your gate is taking an
  unsigned policy.
- Verdict semantics: `pass` mergeable, `warn` mergeable with findings
  rendered, `block` the step fails. The rendered PR comment comes from
  `verdict.json` by template only — no generated prose.
