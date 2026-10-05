"""Run public CLI commands from a non-editable wheel outside the source tree."""

import json
import os
import shutil
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture()
def installed(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", source)
    for directory in ("pr_redteam", "schema"):
        shutil.copytree(
            ROOT / directory, source / directory,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    subprocess.run(
        [sys.executable, "-c",
         "from setuptools.build_meta import build_wheel; "
         "import sys; build_wheel(sys.argv[1])", str(wheels)],
        cwd=source, capture_output=True, text=True, check=True,
    )
    wheel = next(wheels.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        assert archive.read("schema/verdict.schema.json") == (
            ROOT / "schema/verdict.schema.json"
        ).read_bytes()
        metadata = archive.read("pr_redteam-0.1.0.dist-info/METADATA").decode()
        assert "Requires-Dist: ruff==0.6.9\n" in metadata

    installer = tmp_path / "installer"
    venv.EnvBuilder(with_pip=True).create(installer)
    python = installer / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    target = tmp_path / "installed"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-index", "--no-deps",
         "--target", str(target), str(wheel)],
        capture_output=True, text=True, check=True,
    )
    return target


@pytest.mark.parametrize("source, expected, count", [
    ("def answer():\n    return 43\n", "pass", 0),
    ("def answer():\n    return missing_symbol()\n", "block", 1),
])
def test_installed_wheel_run_verify_render(
    tmp_path: Path, installed: Path, source: str, expected: str, count: int,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "app.py").write_text("def answer():\n    return 42\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_text(source)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "head")
    head = git(repo, "rev-parse", "HEAD")
    env = dict(os.environ, PYTHONPATH=str(installed))
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    module = subprocess.run(
        [sys.executable, "-c", "import pr_redteam.cli; print(pr_redteam.cli.__file__)"],
        cwd=repo, env=env, capture_output=True, text=True, check=True,
    )
    assert Path(module.stdout.strip()).resolve() == installed / "pr_redteam/cli.py"
    cli = [sys.executable, "-m", "pr_redteam.cli"]
    generated = subprocess.run(
        [*cli, "run", "--base", base, "--head", head, "--out", "verdict.json"],
        cwd=repo, env=env, capture_output=True, text=True, check=True,
    )
    verdict = json.loads((repo / "verdict.json").read_text())
    assert verdict["verdict"] == expected
    assert verdict["counters"]["unresolvedSymbols"] == count
    verified = subprocess.run(
        [*cli, "verify", "--verdict", "verdict.json"],
        cwd=repo, env=env, capture_output=True, text=True, check=True,
    )
    assert generated.stdout == verified.stdout
    rendered = subprocess.run(
        [*cli, "render", "--verdict", "verdict.json"],
        cwd=repo, env=env, capture_output=True, text=True, check=True,
    )
    assert f"verdict: {expected.upper()}" in rendered.stdout
