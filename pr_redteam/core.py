"""pr_redteam MVP core.

Contract names mirror SPEC.md: collectDiffScope, runStaticGates,
evaluateArchitecturePredicates, verifyRedGreenTests, hashNormalizedVerdict,
renderPrCommentFromVerdict. Step 1 (advisory) wires diff counters, ruff
F821 undefined names, and secret patterns. Architecture predicates and
red-green verification enter in later steps; their counters stay 0 here
and the rendered comment states the wired scope.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

CORE_VERSION = "0.1.0"

SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"xox[bap]-[A-Za-z0-9-]{10,}"),
]

DEPENDENCY_FILES = ("requirements", "pyproject.toml", "package.json", "Pipfile")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def collect_diff_scope(repo: Path, base: str, head: str) -> dict:
    numstat = _git(repo, "diff", "--numstat", f"{base}..{head}")
    files = []
    net_loc = 0
    for line in sorted(numstat.splitlines()):
        added, deleted, path = line.split("\t", 2)
        a = 0 if added == "-" else int(added)
        d = 0 if deleted == "-" else int(deleted)
        net_loc += a - d
        files.append({"path": path, "added": a, "deleted": d})
    return {"files": files, "netLocChanged": net_loc, "filesTouched": len(files)}


def _added_lines(repo: Path, base: str, head: str) -> list[tuple[str, str]]:
    diff = _git(repo, "diff", "--unified=0", f"{base}..{head}")
    out, current = [], ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            out.append((current, line[1:]))
    return out


def count_new_dependencies(added: list[tuple[str, str]]) -> int:
    count = 0
    for path, line in added:
        name = Path(path).name
        if not any(name.startswith(prefix) for prefix in DEPENDENCY_FILES):
            continue
        text = line.strip().strip(",")
        if re.match(r'^"?[A-Za-z0-9_.\-]+\s*(==|>=|~=|>|<|\[|:)', text) or (
            name == "package.json" and re.match(r'^"[A-Za-z0-9@/.\-]+"\s*:', text)
        ):
            count += 1
    return count


def count_secrets(added: list[tuple[str, str]]) -> int:
    return sum(
        1 for _, line in added if any(p.search(line) for p in SECRET_PATTERNS)
    )


def count_unresolved_symbols(repo: Path, base: str, head: str) -> tuple[int, list[dict]]:
    changed = _git(repo, "diff", "--name-only", f"{base}..{head}", "--", "*.py")
    paths = [p for p in sorted(changed.splitlines()) if (repo / p).exists()]
    if not paths:
        return 0, []
    result = subprocess.run(
        ["ruff", "check", "--select", "F821", "--output-format", "json", *paths],
        cwd=repo, capture_output=True, text=True,
    )
    findings = []
    for item in json.loads(result.stdout or "[]"):
        findings.append({
            "gate": "unresolvedSymbols",
            "file": str(Path(item["filename"]).relative_to(repo)),
            "line": int(item["location"]["row"]),
            "evidence": item["message"],
        })
    return len(findings), findings


DEFAULT_PROTECTED_PATHS = (".redteam/", ".github/workflows/", "schema/", "CODEOWNERS")
DEFAULT_TRIAGE_WEIGHTS = {
    "block": 100, "newSmell": 40, "responsibilityShift": 25,
    "protectedPathHit": 20, "newDependency": 10, "packageTouched": 5,
    "safeLargeDeletionBonus": -15,
}


def count_packages_touched(files: list[dict]) -> int:
    packages = set()
    for item in files:
        parts = Path(item["path"]).parts
        if len(parts) >= 2:
            packages.add("/".join(parts[:2]))
        elif parts:
            packages.add(parts[0])
    return len(packages)


def count_protected_path_hits(files: list[dict], protected=DEFAULT_PROTECTED_PATHS) -> int:
    hits = 0
    for item in files:
        path = item["path"]
        if any(path == p.rstrip("/") or path.startswith(p) for p in protected):
            hits += 1
    return hits


def compute_routing(verdict_word: str, counters: dict, actor_kind: str,
                      weights: dict, self_merge_enabled: bool = False) -> dict:
    is_block = verdict_word == "block"
    safe_large_deletion = (
        counters.get("responsibilityShifts", 0) == 0
        and counters.get("newSmells", 0) == 0
        and counters.get("netLocChanged", 0) < 0
    )
    priority = (
        weights["block"] * (1 if is_block else 0)
        + weights["newSmell"] * min(counters.get("newSmells", 0), 5)
        + weights["responsibilityShift"] * min(counters.get("responsibilityShifts", 0), 4)
        + weights["protectedPathHit"] * (1 if counters.get("protectedPathHits", 0) else 0)
        + weights["newDependency"] * min(counters.get("newDependencies", 0), 3)
        + weights["packageTouched"] * min(counters.get("packagesTouched", 0), 4)
        + (weights["safeLargeDeletionBonus"] if safe_large_deletion else 0)
    )
    lane = "agent" if actor_kind == "agent" else "pr"
    review_required = (
        verdict_word in ("warn", "block")
        or counters.get("protectedPathHits", 0) > 0
    )
    self_merge = bool(
        self_merge_enabled and verdict_word == "pass"
        and counters.get("responsibilityShifts", 0) == 0
        and actor_kind == "agent"
    )
    return {"lane": lane, "maintainerReviewRequired": review_required,
            "selfMergeEligible": self_merge,
            "triagePriority": max(priority, 0)}


def evaluate_architecture_predicates(repo: Path, base: str, head: str) -> dict:
    # Step 2 wires arcade-agent predicates. Step 1 reports zeros and the
    # comment renderer states this scope; a zero here is "not run", and
    # the verdict in step 1 never blocks on architecture counters.
    return {"newSmells": 0, "responsibilityShifts": 0,
            "largestComponentEntities": 0, "layerContractViolations": 0}


def build_verdict(repo: Path, base: str, head: str, actor_app: str,
                  run_id: str, policy_hash: str = "mvp-step1",
                  policy_version: int = 1, actor_kind: str = "unknown",
                  agent_id: str = "", task_id: str = "", attempt: int = 0,
                  warn_as_block: bool = False,
                  self_merge_enabled: bool = False) -> dict:
    scope = collect_diff_scope(repo, base, head)
    added = _added_lines(repo, base, head)
    unresolved, findings = count_unresolved_symbols(repo, base, head)
    secrets = count_secrets(added)
    arch = evaluate_architecture_predicates(repo, base, head)
    counters = {
        "netLocChanged": scope["netLocChanged"],
        "filesTouched": scope["filesTouched"],
        "packagesTouched": count_packages_touched(scope["files"]),
        "protectedPathHits": count_protected_path_hits(scope["files"]),
        "largestFileAddedLines": max(
            (f["added"] for f in scope["files"]), default=0
        ),
        "deadCodeCandidates": 0,
        "newDependencies": count_new_dependencies(added),
        "newPublicSymbols": 0,
        "unresolvedSymbols": unresolved,
        "newSmells": arch["newSmells"],
        "responsibilityShifts": arch["responsibilityShifts"],
        "largestComponentEntities": arch["largestComponentEntities"],
        "layerContractViolations": arch["layerContractViolations"],
        "unmappedClaims": 0,
        "redundantCommentLines": 0,
        "secretsFound": secrets,
        "nondeterministicDiffLines": 0,
        "hiddenSpansRemoved": 0,
        "encodedPayloadsFound": 0,
        "nonOwnerCommandAttempts": 0,
    }
    blocked = counters["unresolvedSymbols"] > 0 or counters["secretsFound"] > 0
    warn = counters["newDependencies"] > 0 and actor_kind == "human"
    if warn_as_block and actor_kind == "agent" and counters["newDependencies"] > 0:
        blocked = True
        warn = False
    verdict_word = "block" if blocked else ("warn" if warn else "pass")
    routing = compute_routing(
        verdict_word, counters, actor_kind, DEFAULT_TRIAGE_WEIGHTS,
        self_merge_enabled=self_merge_enabled,
    )
    actor = {"app": actor_app, "runId": run_id, "kind": actor_kind,
             "agentId": agent_id, "taskId": task_id, "attempt": attempt}
    return {
        "schemaVersion": 1,
        "doctrineVersion": "doctrine-v0.1.0-draft",
        "pr": {"baseSha": base, "headSha": head},
        "policy": {"policyVersion": policy_version, "policyHash": policy_hash,
                   "coreVersion": CORE_VERSION},
        "actor": actor,
        "attestation": "",
        "counters": counters,
        "tests": {"redOnBase": False, "greenOnHead": False,
                  "changedLinesCoveredPercent": 0, "mutationSurvivorsSampled": 0},
        "verdict": verdict_word,
        "routing": routing,
        "findings": findings,
    }


def hash_normalized_verdict(verdict: dict) -> str:
    normalized = {k: v for k, v in verdict.items() if k != "attestation"}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def render_pr_comment_from_verdict(verdict: dict, verdict_hash: str) -> str:
    # Keyword-based output, Simple English rules: first line gives the
    # verdict, one fact per line, key: value, no table, no prose.
    c = verdict["counters"]
    if verdict["verdict"] == "block":
        next_action = "fix findings"
    elif verdict.get("routing", {}).get("maintainerReviewRequired"):
        next_action = "owner review"
    else:
        next_action = "none"
    lines = [
        "<!-- pr-redteam-verdict -->",
        f"verdict: {verdict['verdict'].upper()}",
        f"range: {verdict['pr']['baseSha'][:7]}..{verdict['pr']['headSha'][:7]}",
        f"hash: {verdict_hash[:12]}",
        f"filesTouched: {c['filesTouched']}",
        f"netLocChanged: {c['netLocChanged']}",
        f"packagesTouched: {c.get('packagesTouched', 0)}",
        f"protectedPathHits: {c.get('protectedPathHits', 0)}",
        f"largestFileAddedLines: {c.get('largestFileAddedLines', 0)}",
        f"newDependencies: {c['newDependencies']}",
        f"unresolvedSymbols: {c['unresolvedSymbols']}",
        f"secretsFound: {c['secretsFound']}",
    ]
    routing = verdict.get("routing")
    if routing:
        lines += [
            f"lane: {routing['lane']}",
            f"maintainerReviewRequired: "
            f"{str(routing['maintainerReviewRequired']).lower()}",
            f"triagePriority: {routing['triagePriority']}",
            f"selfMergeEligible: {str(routing['selfMergeEligible']).lower()}",
        ]
    if verdict["findings"]:
        for finding in verdict["findings"]:
            lines.append(
                f"finding: {finding['gate']} "
                f"{finding['file']}:{finding['line']} {finding['evidence']}"
            )
    else:
        lines.append("findings: none")
    lines += [
        "notRun: architecture predicates, red-green tests",
        f"nextAction: {next_action}",
    ]
    return "\n".join(lines) + "\n"
