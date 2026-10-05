#!/usr/bin/env python3
"""E2E dogfood for pr_redteam. No unit tests: real git repos, real CLI
subprocess, real verdict.json files. Each scenario is a planted PR.

Usage: python3 scripts/dogfood/e2e_dogfood.py [--repo-root PATH] [--keep]
Exit: 0 all scenarios pass, 1 any fail. Output keyword lines only.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"cmd failed: {cmd}\n{r.stdout}\n{r.stderr}")
    return r

def git(repo, *args):
    return run(["git","-C",str(repo),*args]).stdout.strip()

def make_repo(tmp):
    repo = Path(tmp)/"repo"; repo.mkdir()
    run(["git","init","-q","-b","main",str(repo)])
    git(repo,"config","user.email","dogfood@example.invalid")
    git(repo,"config","user.name","dogfood")
    (repo/"app.py").write_text("def answer():\n    return 42\n")
    git(repo,"add","-A"); git(repo,"commit","-q","-m","base")
    return repo

def commit(repo, files: dict):
    for name, text in files.items():
        p = repo/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
    git(repo,"add","-A"); git(repo,"commit","-q","-m","change")
    return git(repo,"rev-parse","HEAD")

def gate(repo, base, head, policy=None, actor_kind="unknown", extra=None):
    out = repo.parent/"verdict.json"
    cmd = [sys.executable,"-m","pr_redteam.cli","run","--repo",str(repo),
           "--base",base,"--head",head,"--out",str(out),
           "--actor-app","e2e-dogfood","--run-id","e2e-1","--actor-kind",actor_kind]
    if policy: cmd += ["--policy",str(policy)]
    if extra: cmd += extra
    env_path = str(ROOT/".venv"/"bin")
    import os
    env = dict(os.environ); env["PATH"] = env_path+":"+env.get("PATH","")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"gate crash: {r.stdout} {r.stderr}")
    return json.loads(out.read_text()), r.stdout.strip()

RESULTS=[]
def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"{'pass' if cond else 'FAIL'}: {name} {detail}".rstrip())

def scenario(name, fn):
    with tempfile.TemporaryDirectory(prefix="dogfood-") as tmp:
        try: fn(tmp)
        except Exception as e: check(name, False, f"error={e}")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--self-only", action="store_true")
    args = ap.parse_args()
    agent_policy = ROOT/"policy"/"policy.agent.json"
    pr_policy = ROOT/"policy"/"policy.pr.json"

    def s_clean(tmp):
        repo=make_repo(tmp); base=git(repo,"rev-parse","HEAD")
        head=commit(repo,{"app.py":"def answer():\n    return 43\n"})
        v,_=gate(repo,base,head,pr_policy,"human")
        check("clean-pass", v["verdict"]=="pass" and "architecturePredicates" in v["gates"]["notRun"], f"verdict={v['verdict']}")
    scenario("clean", s_clean)

    def s_symbol(tmp):
        repo=make_repo(tmp); base=git(repo,"rev-parse","HEAD")
        head=commit(repo,{"app.py":"def answer():\n    return missing_symbol()\n"})
        v,_=gate(repo,base,head,pr_policy,"human")
        check("invented-symbol-block", v["verdict"]=="block" and v["counters"]["unresolvedSymbols"]==1)
    scenario("symbol", s_symbol)

    def s_secret(tmp):
        repo=make_repo(tmp); base=git(repo,"rev-parse","HEAD")
        tok="ghp_"+"0"*24+"abcdefghij"
        head=commit(repo,{"notes.txt":f"token {tok}\n"})
        v,_=gate(repo,base,head,pr_policy,"human")
        check("secret-block", v["verdict"]=="block" and v["counters"]["secretsFound"]==1)
    scenario("secret", s_secret)

    def s_godfile(tmp):
        repo=make_repo(tmp); base=git(repo,"rev-parse","HEAD")
        big="def f():\n    return 1\n" + "".join(f"    x{i}={i}\n" for i in range(500))
        # build a 500+ line single file
        lines=["def big():"]+[f"    v{i} = {i}" for i in range(500)]+["    return v0"]
        head=commit(repo,{"god.py":"\n".join(lines)+"\n"})
        v,_=gate(repo,base,head,agent_policy,"agent")
        check("agent-godfile-block", v["verdict"]=="block" and v["counters"]["largestFileAddedLines"]>400, f"largest={v['counters']['largestFileAddedLines']} verdict={v['verdict']}")
        v2,_=gate(repo,base,head,pr_policy,"human")
        check("human-godfile-under-pr-cap-pass", v2["verdict"]=="pass", f"verdict={v2['verdict']} prCap=800 largest=502")
    scenario("godfile", s_godfile)

    def s_dep(tmp):
        repo=make_repo(tmp); base=git(repo,"rev-parse","HEAD")
        head=commit(repo,{"requirements.txt":"requests==2.32.0\n"})
        va,_=gate(repo,base,head,agent_policy,"agent")
        check("agent-dependency-block", va["verdict"]=="block", f"verdict={va['verdict']}")
        vh,_=gate(repo,base,head,pr_policy,"human")
        check("human-dependency-warn", vh["verdict"]=="warn", f"verdict={vh['verdict']}")
    scenario("dependency", s_dep)

    def s_protected(tmp):
        repo=make_repo(tmp); base=git(repo,"rev-parse","HEAD")
        head=commit(repo,{"schema/x.json":"{}\n"})
        va,_=gate(repo,base,head,agent_policy,"agent")
        check("agent-protected-block", va["verdict"]=="block" and va["routing"]["maintainerReviewRequired"], f"verdict={va['verdict']}")
        vh,_=gate(repo,base,head,pr_policy,"human")
        check("human-protected-warn-review", vh["verdict"]=="warn" and vh["routing"]["maintainerReviewRequired"], f"verdict={vh['verdict']}")
    scenario("protected", s_protected)

    def s_determinism(tmp):
        repo=make_repo(tmp); base=git(repo,"rev-parse","HEAD")
        head=commit(repo,{"app.py":"def answer():\n    return 44\n"})
        v1,h1=gate(repo,base,head,pr_policy,"human")
        # second run different run-id via direct CLI extra is fixed in gate(); emulate by editing actor after? Use CLI twice with different run-id:
        # gate() fixes run-id, so instead verify hash function excludes run identity via verdict file mutation check in-process is unit-like; do real second CLI:
        out=Path(tmp)/"v2.json"
        import os
        env=dict(os.environ); env["PATH"]=str(ROOT/".venv"/"bin")+":"+env.get("PATH","")
        r=subprocess.run([sys.executable,"-m","pr_redteam.cli","run","--repo",str(repo),"--base",base,"--head",head,"--out",str(out),"--actor-app","e2e-dogfood","--run-id","OTHER-RUN-999","--actor-kind","human","--policy",str(pr_policy)],cwd=ROOT,capture_output=True,text=True,env=env)
        check("determinism-diff-runid", r.returncode==0 and r.stdout.strip()==h1, f"hash1={h1[:12]} hash2={r.stdout.strip()[:12]}")
    scenario("determinism", s_determinism)

    # Self dogfood: gate this repo's own HEAD commit
    try:
        head=git(ROOT,"rev-parse","HEAD"); base=git(ROOT,"rev-parse","HEAD~1")
        v,h=gate(ROOT,base,head,pr_policy,"ci") if False else (None,None)
        # Use temp out via CLI directly to avoid writing into repo
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"verdict.json"
            import os
            env=dict(os.environ); env["PATH"]=str(ROOT/".venv"/"bin")+":"+env.get("PATH","")
            r=subprocess.run([sys.executable,"-m","pr_redteam.cli","run","--repo",str(ROOT),"--base",base,"--head",head,"--out",str(out),"--actor-app","self-dogfood","--run-id","self-1","--actor-kind","ci","--policy",str(pr_policy)],cwd=ROOT,capture_output=True,text=True,env=env)
            ok=r.returncode==0 and out.exists()
            verdict=json.loads(out.read_text())["verdict"] if ok else "crash"
            check("self-dogfood-own-head", ok, f"verdict={verdict} hash={(r.stdout.strip()[:12] if r.returncode==0 else r.stderr[:120])}")
    except Exception as e:
        check("self-dogfood-own-head", False, f"error={e}")

    failed=[n for n,ok,_ in RESULTS if not ok]
    print(f"total: {len(RESULTS)} pass: {len(RESULTS)-len(failed)} fail: {len(failed)}")
    if failed: print("failed: "+", ".join(failed))
    return 1 if failed else 0

if __name__=="__main__":
    raise SystemExit(main())
