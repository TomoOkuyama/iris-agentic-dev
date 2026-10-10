"""improve: what state the improvement loop is in, and what to work on next.

The engine knows the loop and nothing about the project it runs in. Where results live, what the two
arms are called, how to check one task, which scheduled workflow is the nightly: all of it is in
`.improve/project.toml`. To use the loop in another project, copy `.improve/` and rewrite that file.

Two verbs, both free:

    improve status      the nightly, the last full holdout, a ranked worklist, this month's spend
    improve next [id]   take the top worklist item, check the task itself is sound, show what failed

Neither starts a model session or reads a credential. Anything that costs money (re-running a task,
the weekly holdout) is a later verb that shows an estimate first and stops at a cap.

The worklist comes from the newest full holdout record: a JSON file under `results_dir` that matches
`record_glob`, covers at least `min_tasks` tasks, has both the baseline and the treated arm, and has no
run from an excluded side. A task that fails in both arms is first, because whatever is missing is not
the treatment. Then a task the treatment made worse, then the tasks that pass only when treated. The
record contract is in `.improve/README.md`.

Spend comes from the ledger, one JSON object per line with `ts` and `cost_usd`. Until something
writes that file the status says so, because a spend figure nobody records is a guess.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import yaml

#: A kind of worklist item, in the order they are worked.
KINDS = ("both_fail", "treated_worse", "treated_only")
KIND_TEXT = {
    "both_fail": "fails in both arms",
    "treated_worse": "treatment made it worse",
    "treated_only": "passes only when treated",
}
KIND_TEXT_PLURAL = {"treated_only": "pass only when treated"}
KIND_ADVICE = {
    "both_fail": (
        "Read the transcripts, then decide where the missing piece lives: in the treatment, in what "
        "every session already sees, or in the code under test."
    ),
    "treated_worse": "The treated arm did worse. Read why the treatment misled the agent before touching it.",
    "treated_only": (
        "The treatment carries something the baseline does not. If sessions rarely use the treatment "
        "unprompted, move that content to where every session sees it."
    ),
    "ok": "This task passes in both arms; there is nothing to fix.",
}


class ConfigError(Exception):
    """The adapter file is missing or wrong. Never swallowed into a default."""


@dataclass
class Arm:
    arm: str
    label: str


@dataclass
class ValidateRule:
    tasks: Optional[tuple]
    command: tuple
    container: Optional[str]
    env: dict
    start_hint: str


@dataclass
class Config:
    root: Path
    name: str
    results_dir: Path
    tasks_dir: Path
    ledger: Path
    nightly_workflow: str
    record_glob: str
    min_tasks: int
    excluded_sides: tuple
    published_marker: str
    baseline: Arm
    treated: Arm
    per_try_usd: float
    per_week_usd: float
    validate: tuple
    probe: tuple = ()
    transcripts_glob: str = ""


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
    baseline: Optional[dict] = None
    treated: Optional[dict] = None


@dataclass
class Status:
    nightly: Nightly
    measured_at: Optional[str]
    config: Config
    tasks: int = 0
    baseline_passed: int = 0
    treated_passed: int = 0
    published: str = ""
    worklist: list = field(default_factory=list)
    spend_month: Optional[float] = None
    outcomes: dict = field(default_factory=dict)


# ---- the adapter -------------------------------------------------------------------------------

_ALLOWED = {
    "project": {"name", "results_dir", "tasks_dir", "ledger"},
    "nightly": {"workflow"},
    "holdout": {
        "record_glob",
        "min_tasks",
        "excluded_sides",
        "published_marker",
        "transcripts_glob",
        "baseline",
        "treated",
    },
    "environment": {"probe"},
    "budget": {"per_try_usd", "per_week_usd"},
}
_ALLOWED_RULE = {"tasks", "command", "container", "start_hint", "env"}


def _strict(table: dict, allowed: set, where: str) -> None:
    for key in table:
        if key not in allowed:
            raise ConfigError(
                f"unknown key {key!r} in [{where}]; allowed: {', '.join(sorted(allowed))}"
            )


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"no adapter at {path}; the loop needs a project.toml there (see .improve/README.md)"
        )
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    root = path.parent.parent
    for table, allowed in _ALLOWED.items():
        _strict(raw.get(table, {}), allowed, table)
    for extra in set(raw) - set(_ALLOWED) - {"validate"}:
        raise ConfigError(f"unknown table [{extra}]")
    project, holdout = raw.get("project", {}), raw.get("holdout", {})
    for key in ("name", "results_dir", "tasks_dir", "ledger"):
        if key not in project:
            raise ConfigError(f"[project] needs {key!r}")
    for side in ("baseline", "treated"):
        arm = holdout.get(side)
        if not isinstance(arm, dict) or "arm" not in arm:
            raise ConfigError(f"[holdout.{side}] needs 'arm' and 'label'")
        _strict(arm, {"arm", "label"}, f"holdout.{side}")
    rules = []
    for index, rule in enumerate(raw.get("validate", [])):
        _strict(rule, _ALLOWED_RULE, f"validate[{index}]")
        rules.append(
            ValidateRule(
                tasks=tuple(rule["tasks"]) if "tasks" in rule else None,
                command=tuple(rule["command"]),
                container=rule.get("container"),
                env=dict(rule.get("env", {})),
                start_hint=rule.get("start_hint", ""),
            )
        )
    budget = raw.get("budget", {})
    return Config(
        root=root,
        name=project["name"],
        results_dir=root / project["results_dir"],
        tasks_dir=root / project["tasks_dir"],
        ledger=root / project["ledger"],
        nightly_workflow=raw.get("nightly", {}).get("workflow", ""),
        record_glob=holdout.get("record_glob", "*.json"),
        min_tasks=int(holdout.get("min_tasks", 30)),
        excluded_sides=tuple(holdout.get("excluded_sides", [])),
        published_marker=holdout.get("published_marker", ""),
        baseline=Arm(
            holdout["baseline"]["arm"],
            holdout["baseline"].get("label", holdout["baseline"]["arm"]),
        ),
        treated=Arm(
            holdout["treated"]["arm"],
            holdout["treated"].get("label", holdout["treated"]["arm"]),
        ),
        per_try_usd=float(budget.get("per_try_usd", 5)),
        per_week_usd=float(budget.get("per_week_usd", 60)),
        validate=tuple(rules),
        probe=tuple(raw.get("environment", {}).get("probe", [])),
        transcripts_glob=holdout.get("transcripts_glob", ""),
    )


def find_adapter(start: Optional[Path] = None) -> Path:
    here = Path(start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / ".improve" / "project.toml"
        if candidate.exists():
            return candidate
    raise ConfigError("no .improve/project.toml in this directory or any parent")


def rule_for(cfg: Config, task_id: str) -> Optional[ValidateRule]:
    """The first rule that names the task, else the first rule with no task list."""
    for rule in cfg.validate:
        if rule.tasks is not None and task_id in rule.tasks:
            return rule
    for rule in cfg.validate:
        if rule.tasks is None:
            return rule
    return None


# ---- reading the results -----------------------------------------------------------------------


def _load_full_holdouts(cfg: Config):
    """Every record that qualifies as a full holdout, as `(measured_at, path, record)`."""
    found = []
    for path in sorted(cfg.results_dir.glob(cfg.record_glob)):
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        runs = record.get("runs") if isinstance(record, dict) else None
        if not isinstance(runs, list) or not runs:
            continue
        if any(r.get("side") in cfg.excluded_sides for r in runs):
            continue
        if not {cfg.baseline.arm, cfg.treated.arm} <= {r.get("arm") for r in runs}:
            continue
        if len({r.get("task_id") for r in runs}) < cfg.min_tasks:
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


def _task_title(cfg: Config, task_id: str) -> str:
    for path in cfg.tasks_dir.rglob(f"{task_id}.yaml"):
        try:
            prompt = (yaml.safe_load(path.read_text()) or {}).get("prompt") or ""
        except (OSError, yaml.YAMLError):
            return ""
        for line in prompt.splitlines():
            if line.strip():
                return line.strip()
    return ""


def _spend_this_month(cfg: Config, now: datetime) -> Optional[float]:
    if not cfg.ledger.exists():
        return None
    month = now.strftime("%Y-%m")
    total = 0.0
    for line in cfg.ledger.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if str(row.get("ts", "")).startswith(month):
            total += float(row.get("cost_usd") or 0)
    return total


def build_status(
    cfg: Config, *, now: datetime, nightly: Callable[[], Nightly]
) -> Status:
    status = Status(
        nightly=nightly(),
        measured_at=None,
        config=cfg,
        spend_month=_spend_this_month(cfg, now),
    )
    holdouts = _load_full_holdouts(cfg)
    if not holdouts:
        return status
    measured, _path, record = max(holdouts, key=lambda h: h[0])
    status.measured_at = measured

    per_task: dict = {}
    for run in record["runs"]:
        per_task.setdefault(run["task_id"], {}).setdefault(run["arm"], []).append(run)
    items = []
    for task_id, arms in per_task.items():
        if cfg.baseline.arm not in arms or cfg.treated.arm not in arms:
            continue
        base, treated = (
            _arm_summary(arms[cfg.baseline.arm]),
            _arm_summary(arms[cfg.treated.arm]),
        )
        status.outcomes[task_id] = {"baseline": base, "treated": treated}
        status.tasks += 1
        status.baseline_passed += base["passed"]
        status.treated_passed += treated["passed"]
        if not base["passed"] and not treated["passed"]:
            kind = "both_fail"
        elif base["passed"] and not treated["passed"]:
            kind = "treated_worse"
        elif not base["passed"] and treated["passed"]:
            kind = "treated_only"
        else:
            continue
        items.append(Item(task_id, kind, _task_title(cfg, task_id), base, treated))
    items.sort(key=lambda i: (KINDS.index(i.kind), i.task_id))
    status.worklist = items
    if cfg.published_marker:
        for line in record.get("published") or []:
            if cfg.published_marker in line:
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
    cfg, pad = s.config, " " * 21
    lines = [f"{'Nightly canary':<21}{_nightly_line(s.nightly)}"]
    if s.measured_at is None:
        lines.append(
            f"{'Last full holdout':<21}No full holdout run found in the results directory."
        )
    else:
        lines.append(f"{'Last full holdout':<21}{s.measured_at[:10]}, {s.tasks} tasks")
        lines.append(
            f"{pad}{cfg.baseline.label} {s.baseline_passed}/{s.tasks}  ·  "
            f"{cfg.treated.label} {s.treated_passed}/{s.tasks}"
        )
        if s.published:
            lines.append(f"{'Result':<21}{s.published}")
        if not s.worklist:
            lines.append(f"{'Worklist':<21}Nothing is failing in that run.")
        else:
            singles = [i for i in s.worklist if i.kind != "treated_only"]
            treated_only = [i for i in s.worklist if i.kind == "treated_only"]
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
            if treated_only:
                label = "Worklist" if first else ""
                ids = ", ".join(i.task_id for i in treated_only)
                noun = "task" if len(treated_only) == 1 else "tasks"
                lines.append(
                    f"{label:<21}{len(treated_only)} {noun} {KIND_TEXT['treated_only']}: {ids}"
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
            "project": s.config.name,
            "nightly": asdict(s.nightly),
            "measured_at": s.measured_at,
            "tasks": s.tasks,
            "baseline_passed": s.baseline_passed,
            "treated_passed": s.treated_passed,
            "published": s.published,
            "spend_month": s.spend_month,
            "budget": {
                "per_try_usd": s.config.per_try_usd,
                "per_week_usd": s.config.per_week_usd,
            },
            "worklist": [
                {"task_id": i.task_id, "kind": i.kind, "title": i.title}
                for i in s.worklist
            ],
        },
        indent=2,
    )


# ---- validating a task (cached) ----------------------------------------------------------------


def _task_sha(cfg: Config, task_id: str) -> Optional[str]:
    for path in cfg.tasks_dir.rglob(f"{task_id}.yaml"):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return None


def _cache_path(cfg: Config) -> Path:
    return cfg.ledger.parent / "validated.json"


def _validate_cached(cfg, task_id, rule, validator, container_running):
    """`(Validation or None, from_cache)`. None means the task's environment is not running. A task
    already checked at this file content is not checked again: a full check can take a long time."""
    sha = _task_sha(cfg, task_id)
    cache_path = _cache_path(cfg)
    try:
        cache = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(task_id)
    if hit and sha and hit.get("sha") == sha and hit.get("ok"):
        return Validation(True, "checked earlier, task file unchanged"), True
    if rule is not None and rule.container and not container_running(rule.container):
        return None, False
    result = validator(task_id)
    if sha:
        cache[task_id] = {
            "sha": sha,
            "ok": result.ok,
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=2))
        except OSError:
            pass
    return result, False


def _arm_text(label: str, arm: dict) -> str:
    verdict = "passed" if arm["passed"] else "failed"
    extra = f"{arm['tool_calls']} calls, {round(arm['seconds'] or 0)}s"
    if arm["timed_out"]:
        extra += ", hit the clock"
    return f"  {label:<18}{verdict} ({extra})"


def _transcripts(cfg: Config, task_id: str) -> list:
    if not cfg.transcripts_glob:
        return []
    return sorted(
        str(p) for p in cfg.results_dir.glob(cfg.transcripts_glob.format(task=task_id))
    )[:4]


def run_next(args, cfg, nightly, validator, container_running, out, now) -> int:
    status = build_status(cfg, now=now, nightly=nightly)
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
            o = status.outcomes[args.task_id]
            item = Item(
                args.task_id,
                "ok",
                _task_title(cfg, args.task_id),
                o["baseline"],
                o["treated"],
            )
    else:
        if not status.worklist:
            out(f"Nothing is failing in the last holdout ({status.measured_at[:10]}).")
            return 0
        item = status.worklist[0]

    rule = rule_for(cfg, item.task_id)
    validation, _cached = _validate_cached(
        cfg, item.task_id, rule, validator, container_running
    )
    if validation is None:
        out(
            f"{item.task_id} needs {rule.container} to check the task, and it is not running."
        )
        if rule.start_hint:
            out(f"Start it with: {rule.start_hint}")
        return 3

    out(f"{item.task_id}: {KIND_TEXT.get(item.kind, 'passes in both arms')}")
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
    if item.baseline and item.treated:
        out("Last holdout:")
        out(_arm_text(cfg.baseline.label, item.baseline))
        out(_arm_text(cfg.treated.label, item.treated))
        out("")
    found = _transcripts(cfg, item.task_id)
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


def _make_gh_nightly(cfg: Config) -> Callable[[], Nightly]:
    def check() -> Nightly:
        if not cfg.nightly_workflow:
            return Nightly("unknown", "", "no nightly workflow in the adapter")
        try:
            proc = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--workflow",
                    cfg.nightly_workflow,
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
                cwd=cfg.root,
            )
            rows = json.loads(proc.stdout or "[]")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            return Nightly("unknown", "", str(exc)[:80])
        if not rows:
            return Nightly("unknown", "", "no completed run found")
        row = rows[0]
        when = str(row.get("createdAt", ""))[:10]
        return (
            Nightly("green", when)
            if row.get("conclusion") == "success"
            else Nightly("red", when, str(row.get("conclusion")))
        )

    return check


def _make_probe(cfg: Config) -> Callable[[str], bool]:
    def running(name: str) -> bool:
        if not cfg.probe:
            return True  # no probe in the adapter: assume the environment is there
        try:
            proc = subprocess.run(
                [part.replace("{name}", name) for part in cfg.probe],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return name in proc.stdout.split()

    return running


def _make_validator(cfg: Config) -> Callable[[str], Validation]:
    def validate(task_id: str) -> Validation:
        rule = rule_for(cfg, task_id)
        if rule is None:
            return Validation(
                False, "the adapter has no [[validate]] rule for this task"
            )
        env = dict(os.environ)
        env.update(rule.env)
        proc = subprocess.run(
            [part.replace("{task}", task_id) for part in rule.command],
            cwd=cfg.root,
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]
        if proc.returncode == 0:
            return Validation(True, "its reference solution passes its check")
        return Validation(False, tail[0] or f"the check exited {proc.returncode}")

    return validate


# ---- entry point -------------------------------------------------------------------------------


def main(
    argv=None,
    *,
    config: Optional[Config] = None,
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

    try:
        cfg = config or load_config(find_adapter())
    except ConfigError as exc:
        out(f"improve: {exc}")
        return 4
    nightly = nightly or _make_gh_nightly(cfg)
    validator = validator or _make_validator(cfg)
    container_running = container_running or _make_probe(cfg)
    now = now or datetime.now(timezone.utc)

    if args.verb == "status":
        status = build_status(cfg, now=now, nightly=nightly)
        out(status_json(status) if args.json else render_status(status))
        return 0
    return run_next(args, cfg, nightly, validator, container_running, out, now)


if __name__ == "__main__":
    sys.exit(main())
