"""improve: one place that says what state the improvement loop is in and what to work on next.

The loop was three CLIs (`skill_eval`, `ladder`, `optimize`) and about twenty flags, and nothing that
said what to do. This is the front of a simpler one. It has two verbs, and both are free:

    improve status      the nightly, the last full holdout, a ranked worklist, this month's spend
    improve next [id]   take the top worklist item, check the task itself is sound, show what failed

Neither starts a model session or reads a credential. Anything that costs money (re-running a task,
the weekly holdout) is a later verb that shows an estimate first and stops at a cap.

The worklist comes from the newest full holdout record under `tests/e2e/results/`: a record with at
least 30 tasks, both the `tools` and `tools+skills` arms, and no train-side runs. A task that fails in
both arms is first, because the missing piece is not in a skill. Then a task the skills made worse,
then the tasks that pass only with skills loaded.

Spend comes from `improve-ledger.jsonl` next to the results, one JSON object per line with `ts` and
`cost_usd`. Until something writes that file the status says so, because a spend figure nobody records
is a guess.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml

REPO = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPO / "tests" / "e2e" / "results"
TASKS_DIR = REPO / "tests" / "e2e" / "tasks" / "benchmark"

#: A record this small is a spot check, not the figure to report.
FULL_HOLDOUT_MIN_TASKS = 30
LEDGER = "improve-ledger.jsonl"
VALIDATED = "improve-validated.json"

#: The kinds of worklist item, in the order they are worked.
KINDS = ("both_fail", "skills_hurt", "skills_only")
KIND_TEXT = {
    "both_fail": "fails in both arms",
    "skills_hurt": "skills made it worse",
    "skills_only": "passes only with skills loaded",
}
KIND_ADVICE = {
    "both_fail": (
        "Read the transcripts, then decide where the missing piece lives: a skill, a tool "
        "description or hint, or a tool bug."
    ),
    "skills_hurt": "The skills arm did worse. Read why the skill misled the agent before touching it.",
    "skills_only": (
        "A skill carries something the tools alone do not. Sessions rarely load skills unprompted, "
        "so consider moving that content to a tool hint."
    ),
    "ok": "This task passes in both arms; there is nothing to fix.",
}

#: Tasks that run on the AI Hub instance instead of iris-dev-iris.
AIHUB_TASKS = ("SKILL-22", "SKILL-23", "SKILL-24", "SKILL-25")


@dataclass
class Nightly:
    state: str  # green | red | unknown
    when: str
    detail: str = ""


@dataclass
class Validation:
    ok: bool
    detail: str = ""


@dataclass
class Item:
    task_id: str
    kind: str
    title: str = ""
    tools: Optional[dict] = None
    skills: Optional[dict] = None


@dataclass
class Status:
    nightly: Nightly
    measured_at: Optional[str]
    tasks: int = 0
    tools_passed: int = 0
    skills_passed: int = 0
    published: str = ""
    worklist: list = field(default_factory=list)
    spend_month: Optional[float] = None
    outcomes: dict = field(default_factory=dict)


# ---- reading the results -----------------------------------------------------------------------


def _load_full_holdouts(results_dir: Path):
    """Every record that qualifies as a full holdout, as `(measured_at, path, record)`."""
    found = []
    for path in sorted(results_dir.glob("ladder-*.json")):
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        runs = record.get("runs") if isinstance(record, dict) else None
        if not isinstance(runs, list) or not runs:
            continue
        if any(r.get("side") == "train" for r in runs):
            continue
        arms = {r.get("arm") for r in runs}
        if not {"tools", "tools+skills"} <= arms:
            continue
        if len({r.get("task_id") for r in runs}) < FULL_HOLDOUT_MIN_TASKS:
            continue
        measured = (record.get("provenance") or {}).get("measured_at")
        if not measured:
            measured = datetime.fromtimestamp(
                path.stat().st_mtime, timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        found.append((measured, path, record))
    return found


def _arm_summary(runs: list) -> dict:
    passed = sum(1 for r in runs if r.get("passed"))
    first = runs[0]
    return {
        "passed": passed * 2 > len(runs),
        "runs": len(runs),
        "tool_calls": first.get("tool_calls"),
        "seconds": first.get("seconds"),
        "timed_out": bool(first.get("timed_out")),
    }


def _task_title(tasks_dir: Path, task_id: str) -> str:
    for path in tasks_dir.rglob(f"{task_id}.yaml"):
        try:
            prompt = (yaml.safe_load(path.read_text()) or {}).get("prompt") or ""
        except (OSError, yaml.YAMLError):
            return ""
        for line in prompt.splitlines():
            if line.strip():
                return line.strip()
    return ""


def _spend_this_month(results_dir: Path, now: datetime) -> Optional[float]:
    ledger = results_dir / LEDGER
    if not ledger.exists():
        return None
    month = now.strftime("%Y-%m")
    total = 0.0
    for line in ledger.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if str(row.get("ts", "")).startswith(month):
            total += float(row.get("cost_usd") or 0)
    return total


def build_status(
    results_dir: Path, tasks_dir: Path, *, now: datetime, nightly: Callable[[], Nightly]
) -> Status:
    status = Status(
        nightly=nightly(),
        measured_at=None,
        spend_month=_spend_this_month(results_dir, now),
    )
    holdouts = _load_full_holdouts(results_dir)
    if not holdouts:
        return status
    measured, _path, record = max(holdouts, key=lambda h: h[0])
    status.measured_at = measured

    per_task: dict = {}
    for run in record["runs"]:
        per_task.setdefault(run["task_id"], {}).setdefault(run["arm"], []).append(run)
    items = []
    for task_id, arms in per_task.items():
        if "tools" not in arms or "tools+skills" not in arms:
            continue
        tools, skills = _arm_summary(arms["tools"]), _arm_summary(arms["tools+skills"])
        status.outcomes[task_id] = {"tools": tools, "skills": skills}
        status.tasks += 1
        status.tools_passed += tools["passed"]
        status.skills_passed += skills["passed"]
        if not tools["passed"] and not skills["passed"]:
            kind = "both_fail"
        elif tools["passed"] and not skills["passed"]:
            kind = "skills_hurt"
        elif not tools["passed"] and skills["passed"]:
            kind = "skills_only"
        else:
            continue
        items.append(
            Item(task_id, kind, _task_title(tasks_dir, task_id), tools, skills)
        )
    items.sort(key=lambda i: (KINDS.index(i.kind), i.task_id))
    status.worklist = items
    for line in record.get("published") or []:
        if "tools -> tools+skills" in line:
            status.published = line
    return status


# ---- rendering ---------------------------------------------------------------------------------


def _nightly_line(n: Nightly) -> str:
    if n.state == "green":
        return f"green ({n.when})"
    if n.state == "red":
        return f"RED ({n.when}). Fix the nightly first."
    return "unknown (could not ask GitHub)" + (f": {n.detail}" if n.detail else "")


def render_status(s: Status) -> str:
    pad = " " * 21
    lines = [f"{'Nightly canary':<21}{_nightly_line(s.nightly)}"]
    if s.measured_at is None:
        lines.append(
            f"{'Last full holdout':<21}No full holdout run found in the results directory."
        )
    else:
        lines.append(f"{'Last full holdout':<21}{s.measured_at[:10]}, {s.tasks} tasks")
        lines.append(
            f"{pad}tools alone {s.tools_passed}/{s.tasks}  ·  with skills {s.skills_passed}/{s.tasks}"
        )
        if s.published:
            lines.append(f"{'Result':<21}{s.published}")
        if not s.worklist:
            lines.append(f"{'Worklist':<21}Nothing is failing in that run.")
        else:
            singles = [i for i in s.worklist if i.kind != "skills_only"]
            skills_only = [i for i in s.worklist if i.kind == "skills_only"]
            first = True
            for n, item in enumerate(singles, 1):
                label = "Worklist" if first else ""
                first = False
                marker = "   <- next" if n == 1 else ""
                lines.append(
                    f"{label:<21}{n}. {item.task_id}  {KIND_TEXT[item.kind]}{marker}"
                )
                if item.title:
                    lines.append(f"{pad}   {item.title[:90]}")
            if skills_only:
                label = "Worklist" if first else ""
                ids = ", ".join(i.task_id for i in skills_only)
                lines.append(
                    f"{label:<21}{len(skills_only)} tasks {KIND_TEXT['skills_only']}: {ids}"
                )
    spend = "not tracked yet" if s.spend_month is None else f"${s.spend_month:.2f}"
    lines.append(f"{'Spend this month':<21}{spend}")
    if s.nightly.state == "red":
        nxt = "Fix the nightly, then `improve next`."
    elif s.worklist:
        nxt = "improve next"
    else:
        nxt = "Nothing to do; run the weekly holdout when it is due."
    lines.append(f"{'Next':<21}{nxt}")
    return "\n".join(lines)


def status_json(s: Status) -> str:
    return json.dumps(
        {
            "nightly": asdict(s.nightly),
            "measured_at": s.measured_at,
            "tasks": s.tasks,
            "tools_passed": s.tools_passed,
            "skills_passed": s.skills_passed,
            "published": s.published,
            "spend_month": s.spend_month,
            "worklist": [
                {"task_id": i.task_id, "kind": i.kind, "title": i.title}
                for i in s.worklist
            ],
        },
        indent=2,
    )


# ---- validating a task (cached) ----------------------------------------------------------------


def _task_sha(tasks_dir: Path, task_id: str) -> Optional[str]:
    for path in tasks_dir.rglob(f"{task_id}.yaml"):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def _validate_cached(
    results_dir, tasks_dir, task_id, validator, container_running, container
):
    """`(Validation, from_cache)`. A task already checked at this file content is not checked again:
    the full check takes about eighteen minutes across the corpus."""
    sha = _task_sha(tasks_dir, task_id)
    cache_path = results_dir / VALIDATED
    try:
        cache = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(task_id)
    if hit and sha and hit.get("sha") == sha and hit.get("ok"):
        return Validation(True, "checked earlier, task file unchanged"), True
    if not container_running(container):
        return None, False
    result = validator(task_id)
    if sha:
        cache[task_id] = {
            "sha": sha,
            "ok": result.ok,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        try:
            results_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=2))
        except OSError:
            pass
    return result, False


def _arm_text(label: str, arm: dict) -> str:
    verdict = "passed" if arm["passed"] else "failed"
    extra = f"{arm['tool_calls']} calls, {round(arm['seconds'] or 0)}s"
    if arm["timed_out"]:
        extra += ", hit the clock"
    return f"  {label:<13}{verdict} ({extra})"


def _transcripts(results_dir: Path, task_id: str) -> list:
    return sorted(
        str(p) for p in results_dir.glob(f"ladder-*.transcripts/{task_id}__*")
    )[:4]


def run_next(
    args, results_dir, tasks_dir, nightly, validator, container_running, out, now
) -> int:
    status = build_status(results_dir, tasks_dir, now=now, nightly=nightly)
    if status.measured_at is None:
        out(
            "No full holdout run found in the results directory, so there is no worklist yet."
        )
        return 0
    if args.task_id:
        if args.task_id not in status.outcomes:
            out(
                f"{args.task_id} is not in the last holdout ({status.measured_at[:10]})."
            )
            return 2
        item = next((i for i in status.worklist if i.task_id == args.task_id), None)
        if item is None:
            item = Item(
                args.task_id,
                "ok",
                _task_title(tasks_dir, args.task_id),
                status.outcomes[args.task_id]["tools"],
                status.outcomes[args.task_id]["skills"],
            )
    else:
        if not status.worklist:
            out(f"Nothing is failing in the last holdout ({status.measured_at[:10]}).")
            return 0
        item = status.worklist[0]

    container = "iad-aihub-iris" if item.task_id in AIHUB_TASKS else "iris-dev-iris"
    validation, cached = _validate_cached(
        results_dir, tasks_dir, item.task_id, validator, container_running, container
    )
    if validation is None:
        out(
            f"{item.task_id} needs the {container} container to check the task, and it is not running."
        )
        out(f"Start it with: docker start {container}")
        return 3

    heading = KIND_TEXT.get(item.kind, "passes in both arms")
    out(f"{item.task_id}: {heading}")
    if item.title:
        out(f"  {item.title}")
    out("")
    if validation.ok:
        out(
            f"The task is sound ({validation.detail or 'its reference solution passes its check'})."
        )
    else:
        out(f"The task is broken: {validation.detail}")
        out("Fix the task before blaming the agent.")
    out("")
    if item.tools and item.skills:
        out("Last holdout:")
        out(_arm_text("tools alone", item.tools))
        out(_arm_text("with skills", item.skills))
        out("")
    found = _transcripts(results_dir, item.task_id)
    if found:
        out("Transcripts to read:")
        for path in found:
            out(f"  {path}")
    else:
        out(
            "No transcripts were recorded for this run, so there is nothing to read yet."
        )
        out(
            f"`improve try {item.task_id}` would re-run it and keep them (it costs money and will ask first)."
        )
    out("")
    out(KIND_ADVICE.get(item.kind, KIND_ADVICE["ok"]))
    return 0 if validation.ok else 1


# ---- the defaults that shell out (injected in tests) --------------------------------------------


def _gh_nightly() -> Nightly:
    try:
        proc = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                "skill-regression.yml",
                "--status",
                "completed",
                "--limit",
                "1",
                "--json",
                "conclusion,createdAt,event",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        rows = json.loads(proc.stdout or "[]")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return Nightly("unknown", "", str(exc)[:80])
    if not rows:
        return Nightly("unknown", "", "no completed run found")
    row = rows[0]
    when = str(row.get("createdAt", ""))[:10]
    if row.get("conclusion") == "success":
        return Nightly("green", when)
    return Nightly("red", when, str(row.get("conclusion")))


def _docker_running(name: str) -> bool:
    try:
        proc = subprocess.run(
            ["docker", "ps", "--filter", f"name=^/{name}$", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return name in proc.stdout.split()


def _pytest_validator(task_id: str) -> Validation:
    """The committed check for one task: false before, true after its reference solution."""
    aihub = task_id in AIHUB_TASKS
    selector = (
        f"ai_hub and {task_id}"
        if aihub
        else f"every_committed_task_is_false_before_and_true_after and {task_id}"
    )
    env = dict(os.environ)
    env.update(
        {
            "IRIS_HOST": "localhost",
            "IRIS_USERNAME": "_SYSTEM",
            "IRIS_PASSWORD": "SYS",
            "PYTHONPATH": str(REPO),
        }
        | (
            {"IRIS_WEB_PORT": "52781", "IRIS_CONTAINER": "iad-aihub-iris"}
            if aihub
            else {"IRIS_WEB_PORT": "52780", "IRIS_CONTAINER": "iris-dev-iris"}
        )
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/e2e/skill_eval/test_graded_task_live.py",
            "-k",
            selector,
            "-q",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]
    if proc.returncode == 0 and " passed" in tail[0]:
        return Validation(True, "its reference solution passes its check")
    if (
        "no tests ran" in tail[0]
        or "deselected" in tail[0]
        and " passed" not in tail[0]
    ):
        return Validation(
            False, f"no live check is registered for {task_id} here ({tail[0]})"
        )
    return Validation(False, tail[0] or "the live check failed")


# ---- entry point -------------------------------------------------------------------------------


def main(
    argv=None,
    *,
    results_dir: Path = RESULTS_DIR,
    tasks_dir: Path = TASKS_DIR,
    nightly: Optional[Callable[[], Nightly]] = None,
    validator: Optional[Callable[[str], Validation]] = None,
    container_running: Optional[Callable[[str], bool]] = None,
    out: Callable[[str], None] = print,
    now: Optional[datetime] = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="improve",
        description="The improvement loop: what state it is in, and what to work on next. Free to run.",
    )
    sub = parser.add_subparsers(dest="verb", required=True)
    p_status = sub.add_parser(
        "status", help="the nightly, the last full holdout, the worklist, the spend"
    )
    p_status.add_argument(
        "--json", action="store_true", help="machine-readable, for a morning brief"
    )
    p_next = sub.add_parser(
        "next", help="take the top worklist item and check the task is sound"
    )
    p_next.add_argument(
        "task_id", nargs="?", help="work this task instead of the top item"
    )
    args = parser.parse_args(argv)

    nightly = nightly or _gh_nightly
    validator = validator or _pytest_validator
    container_running = container_running or _docker_running
    now = now or datetime.now(timezone.utc)

    if args.verb == "status":
        status = build_status(
            Path(results_dir), Path(tasks_dir), now=now, nightly=nightly
        )
        out(status_json(status) if args.json else render_status(status))
        return 0
    return run_next(
        args,
        Path(results_dir),
        Path(tasks_dir),
        nightly,
        validator,
        container_running,
        out,
        now,
    )


if __name__ == "__main__":
    sys.exit(main())
