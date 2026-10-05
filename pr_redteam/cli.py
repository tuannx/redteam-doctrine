"""CLI: run | verify | render. See SPEC.md run profiles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

from .core import (
    build_verdict,
    hash_normalized_verdict,
    render_pr_comment_from_verdict,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "verdict.schema.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _load_policy(path: str | None) -> tuple[dict, str, int]:
    if not path:
        return {}, "mvp-step1", 1
    raw = Path(path).read_bytes()
    policy = json.loads(raw)
    import hashlib
    return policy, hashlib.sha256(raw).hexdigest()[:16], int(policy.get("policyVersion", 1))


def cmd_run(args: argparse.Namespace) -> int:
    policy, policy_hash, policy_version = _load_policy(args.policy)
    verdict = build_verdict(
        Path(args.repo), args.base, args.head, args.actor_app, args.run_id,
        policy_hash=policy_hash, policy_version=policy_version,
        actor_kind=args.actor_kind, agent_id=args.agent_id,
        task_id=args.task_id, attempt=args.attempt, policy=policy,
    )
    jsonschema.validate(verdict, _load_schema())
    Path(args.out).write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    print(hash_normalized_verdict(verdict))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    verdict = json.loads(Path(args.verdict).read_text())
    jsonschema.validate(verdict, _load_schema())
    print(hash_normalized_verdict(verdict))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    verdict = json.loads(Path(args.verdict).read_text())
    sys.stdout.write(
        render_pr_comment_from_verdict(verdict, hash_normalized_verdict(verdict))
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="pr_redteam")
    sub = parser.add_subparsers(required=True)

    run = sub.add_parser("run")
    run.add_argument("--repo", default=".")
    run.add_argument("--base", required=True)
    run.add_argument("--head", required=True)
    run.add_argument("--out", default="verdict.json")
    run.add_argument("--actor-app", default="pr-redteam")
    run.add_argument("--run-id", default="local")
    run.add_argument("--policy", default=None)
    run.add_argument("--actor-kind", default="unknown",
                     choices=["human", "agent", "ci", "unknown"])
    run.add_argument("--agent-id", default="")
    run.add_argument("--task-id", default="")
    run.add_argument("--attempt", type=int, default=0)
    run.set_defaults(func=cmd_run)

    verify = sub.add_parser("verify")
    verify.add_argument("--verdict", required=True)
    verify.set_defaults(func=cmd_verify)

    render = sub.add_parser("render")
    render.add_argument("--verdict", required=True)
    render.set_defaults(func=cmd_render)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
