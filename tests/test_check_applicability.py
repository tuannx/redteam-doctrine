"""Tests for issue #5: unresolvedSymbols applicability metadata.

A TypeScript-only change used to report unresolvedSymbols=0 + pass,
indistinguishable from a measured-clean Python check. build_verdict now
emits checks.unresolvedSymbols (measured|unsupported|notRun) plus the
unsupported file list, and the renderer states it.
"""

import json
import subprocess
from pathlib import Path

import jsonschema

from pr_redteam.core import build_verdict, render_pr_comment_from_verdict, hash_normalized_verdict

SCHEMA = json.loads(
    (Path(__file__).parent.parent / "schema" / "verdict.schema.json").read_text()
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _verdict(tmp_path: Path, files: dict[str, str]) -> dict:
    repo = tmp_path / "fixture"
    subprocess.run(["git", "init", "-b", "main", "-q", str(repo)], check=True)
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "README.md").write_text("base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    for rel, text in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD")
    return build_verdict(repo, base, head, "test", "applicability")


TS_BAD = "export function answer(): number { return absent_symbol(); }\n"
TS_CLEAN = "export function answer(): number { return 42; }\n"
PY_BAD = "def answer():\n    return missing_symbol\n"


def test_typescript_only_is_unsupported(tmp_path: Path) -> None:
    for index, text in enumerate((TS_BAD, TS_CLEAN)):
        case = tmp_path / f"case{index}"
        case.mkdir()
        verdict = _verdict(case, {"app.ts": text})
        jsonschema.validate(verdict, SCHEMA)
        assert verdict["counters"]["unresolvedSymbols"] == 0
        assert verdict["checks"]["unresolvedSymbols"] == "unsupported"
        assert verdict["checks"]["unsupportedFiles"] == ["app.ts"]
        comment = render_pr_comment_from_verdict(
            verdict, hash_normalized_verdict(verdict)
        )
        assert "unresolvedSymbolsCheck: unsupported" in comment
        assert "unsupportedFiles: app.ts" in comment


def test_python_bad_is_measured(tmp_path: Path) -> None:
    verdict = _verdict(tmp_path, {"app.py": PY_BAD})
    jsonschema.validate(verdict, SCHEMA)
    assert verdict["checks"]["unresolvedSymbols"] == "measured"
    assert verdict["checks"]["unsupportedFiles"] == []
    assert verdict["counters"]["unresolvedSymbols"] == 1
    assert verdict["verdict"] == "block"


def test_mixed_python_and_typescript(tmp_path: Path) -> None:
    verdict = _verdict(tmp_path, {"app.py": PY_BAD, "app.ts": TS_BAD})
    jsonschema.validate(verdict, SCHEMA)
    assert verdict["checks"]["unresolvedSymbols"] == "measured"
    assert verdict["checks"]["unsupportedFiles"] == ["app.ts"]
    assert verdict["counters"]["unresolvedSymbols"] == 1


def test_docs_only_is_not_run(tmp_path: Path) -> None:
    verdict = _verdict(tmp_path, {"README.md": "changed\n"})
    jsonschema.validate(verdict, SCHEMA)
    assert verdict["checks"]["unresolvedSymbols"] == "notRun"
    assert verdict["checks"]["unsupportedFiles"] == []
