"""improve: what state the improvement loop is in, and what to work on next.

The engine knows the loop and nothing about the project it runs in. Where results live, what the two
arms are called, how to check one task, which scheduled workflow is the nightly: all of it is in
`.improve/project.toml`. To use the loop in another project, copy `.improve/` and rewrite that file.

Three verbs. The first two are free:

    improve status      the nightly, the last full holdout, a ranked worklist, this month's spend
    improve next [id]   take the top worklist item, check the task itself is sound, show what failed
    improve try [id]    re-run one task after a change and say whether it helped. This one spends.

`status` and `next` never start a model session or read a credential. `try` shows the harness's own
estimate, asks, passes a cap to the run, and writes every step to the ledger under an `IMP-NNNN` id. The
cap is the bound, not the estimate: estimates have run several times low.

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
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
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
class TryRule:
    tasks: Optional[tuple]
    command: tuple
    dry_run_flag: str
    repeats: int
    cost_regex: str
    env: dict
    timeout_seconds: int
    estimate_note: str
    # A treatment that is one arm per task: the treated sessions are the arms starting with this.
    treated_prefix: str = ""
    # A per-session field saying whether the treatment was applied; counted so an arm nobody used is seen.
    applied_field: str = ""
    applied_label: str = ""
    # Earlier run files (JSON with "runs", or one run per line) to compare with when a task is not in
    # the full holdout. Used only for tasks this rule names.
    before_glob: str = ""
    # Report a change in calls when the pass counts do not move.
    judge_calls: bool = False
    # Arms that start with the prefix but are not a per-task treatment.
    treated_exclude: tuple = ()


@dataclass
class MeasureRule:
    """How to run the harness for one subject (135). `{subject}`, `{side}`, `{repeats}`, `{cap}` and
    `{spent}` are filled in; the run file is found in the output with `runs_file_regex`."""

    command: tuple
    dry_run_flag: str
    repeats: int
    cost_regex: str
    runs_file_regex: str
    env: dict
    timeout_seconds: int
    estimate_note: str
    # Extra arguments only for a run whose result may become a verdict (a held-out run).
    verdict_args: tuple = ()
    # The subjects this rule is for; a rule with none is the default for every other subject.
    subjects: tuple = ()


@dataclass
class RunResult:
    returncode: int
    stdout: str


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
    tries: tuple = ()
    # 135: a programme budget on top of the weekly guard. Zero means no such limit.
    total_usd: float = 0.0
    per_subject_usd: float = 0.0
    per_measure_usd: float = 0.0
    checkpoint_usd: float = 0.0
    # Spend before this timestamp is not counted against total_usd and per_subject_usd.
    budget_since: str = ""
    # A file whose sha256 is written on every run event, so a verdict can refuse a changed criterion.
    criteria: str = ""
    report_command: tuple = ()
    aliases: dict = field(default_factory=dict)
    measures: tuple = ()


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
    "budget": {
        "per_try_usd",
        "per_week_usd",
        "total_usd",
        "per_subject_usd",
        "per_measure_usd",
        "checkpoint_usd",
        "since",
    },
    "evidence": {"criteria"},
    "report": {"command"},
}
_ALLOWED_MEASURE = {
    "command", "dry_run_flag", "repeats", "cost_regex", "runs_file_regex", "env", "timeout_seconds",
    "estimate_note", "verdict_args", "subjects",
}
_ALLOWED_RULE = {"tasks", "command", "container", "start_hint", "env"}
_ALLOWED_TRY = {
    "tasks", "command", "dry_run_flag", "repeats", "cost_regex", "env", "timeout_seconds",
    "estimate_note", "treated_prefix", "applied_field", "applied_label", "before_glob", "judge_calls", "treated_exclude",
}


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
    for extra in set(raw) - set(_ALLOWED) - {"validate", "try", "measure", "alias"}:
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
    tries = []
    for index, rule in enumerate(raw.get("try", [])):
        _strict(rule, _ALLOWED_TRY, f"try[{index}]")
        if "command" not in rule:
            raise ConfigError(f"[[try]] #{index + 1} needs a 'command'")
        tries.append(TryRule(
            tasks=tuple(rule["tasks"]) if "tasks" in rule else None,
            command=tuple(rule["command"]),
            dry_run_flag=rule.get("dry_run_flag", "--dry-run"),
            repeats=int(rule.get("repeats", 3)),
            cost_regex=rule.get("cost_regex", ""),
            env=dict(rule.get("env", {})),
            timeout_seconds=int(rule.get("timeout_seconds", 3600)),
            estimate_note=rule.get("estimate_note", ""),
            treated_prefix=rule.get("treated_prefix", ""),
            applied_field=rule.get("applied_field", ""),
            applied_label=rule.get("applied_label", ""),
            before_glob=rule.get("before_glob", ""),
            judge_calls=bool(rule.get("judge_calls", False)),
            treated_exclude=tuple(rule.get("treated_exclude", [])),
        ))
    measures = []
    for index, rule in enumerate(raw.get("measure", [])):
        _strict(rule, _ALLOWED_MEASURE, f"measure[{index}]")
        for key in ("command", "runs_file_regex", "cost_regex"):
            if key not in rule:
                raise ConfigError(f"[[measure]] #{index + 1} needs {key!r}")
        measures.append(MeasureRule(
            command=tuple(rule["command"]),
            dry_run_flag=rule.get("dry_run_flag", "--dry-run"),
            repeats=int(rule.get("repeats", 3)),
            cost_regex=rule["cost_regex"],
            runs_file_regex=rule["runs_file_regex"],
            env=dict(rule.get("env", {})),
            timeout_seconds=int(rule.get("timeout_seconds", 14400)),
            estimate_note=rule.get("estimate_note", ""),
            verdict_args=tuple(rule.get("verdict_args", [])),
            subjects=tuple(rule.get("subjects", [])),
        ))
    budget = raw.get("budget", {})
    criteria = raw.get("evidence", {}).get("criteria", "")
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
        tries=tuple(tries),
        total_usd=float(budget.get("total_usd", 0)),
        per_subject_usd=float(budget.get("per_subject_usd", 0)),
        per_measure_usd=float(budget.get("per_measure_usd", 0)),
        checkpoint_usd=float(budget.get("checkpoint_usd", 0)),
        budget_since=str(budget.get("since", "")),
        criteria=str(root / criteria) if criteria else "",
        report_command=tuple(raw.get("report", {}).get("command", [])),
        aliases=dict(raw.get("alias", {})),
        measures=tuple(measures),
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


def try_rule_for(cfg: Config, task_id: str) -> Optional[TryRule]:
    """The first rule that names the task, else the first rule with no task list."""
    for rule in cfg.tries:
        if rule.tasks is not None and task_id in rule.tasks:
            return rule
    for rule in cfg.tries:
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
        "passes": passed,
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


# ---- the ledger --------------------------------------------------------------------------------


def read_ledger(cfg: Config) -> list:
    if not cfg.ledger.exists():
        return []
    events = []
    for line in cfg.ledger.read_text().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def append_ledger(cfg: Config, event: dict) -> None:
    """Append-only: one line per event, never rewritten."""
    cfg.ledger.parent.mkdir(parents=True, exist_ok=True)
    with cfg.ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")


def next_imp_id(events: list) -> str:
    top = 0
    for event in events:
        match = re.fullmatch(r"IMP-(\d+)", str(event.get("id", "")))
        if match:
            top = max(top, int(match.group(1)))
    return f"IMP-{top + 1:04d}"


def open_iteration(events: list, task_id: str) -> Optional[dict]:
    """The claim on this task that no verdict has closed yet, if any."""
    open_claim = None
    for event in events:
        if event.get("task") != task_id and event.get("event") != "verdict":
            continue
        if event.get("event") == "claim" and event.get("task") == task_id:
            open_claim = event
        elif event.get("event") == "verdict" and open_claim and event.get("id") == open_claim.get("id"):
            open_claim = None
    return open_claim


def _iso_week(ts: str):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).isocalendar()[:2]
    except ValueError:
        return None


def spend_this_week(events: list, now: datetime) -> float:
    week = now.isocalendar()[:2]
    return sum(float(e.get("cost_usd") or 0) for e in events if _iso_week(str(e.get("ts", ""))) == week)


#: A change in an arm's pass rate counts only when it is at least this much. With three repeats, one
#: extra pass is a third and is within the noise of an unchanged setup; the first real run is the
#: reason: nothing had been changed, one session in six passed, and a smaller band called it "better".
NOISE_BAND = 0.5
#: When the pass counts do not move, a treated arm that needs this much fewer or more calls than it
#: did before is "cheaper" or "costlier". Calls are a noisy cost at three repeats, so the band is wide.
CALLS_BAND = 0.25


def judge(before: dict, after: dict) -> str:
    """One word for what a re-run says about a change. `before` and `after` map an arm to
    `(passes, runs)`. A move smaller than `NOISE_BAND` is no move. Three repeats show a direction,
    not proof, and the caller says so."""
    up = down = False
    failing_before = []
    for arm, (b_pass, b_runs) in before.items():
        a_pass, a_runs = after[arm]
        rate_b, rate_a = b_pass / b_runs, a_pass / a_runs
        up |= rate_a - rate_b >= NOISE_BAND - 1e-9
        down |= rate_b - rate_a >= NOISE_BAND - 1e-9
        if rate_b < 0.5:
            failing_before.append(arm)
    if up and down:
        return "mixed"
    if down:
        return "worse"
    if not up:
        return "no change"
    if failing_before and all(after[a][0] == after[a][1] for a in failing_before):
        return "fixed"
    return "better"



def _read_runs(path: Path) -> list:
    """The runs in a result file: JSON with a "runs" list, or one JSON run per line."""
    try:
        text = path.read_text()
    except OSError:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("runs"), list):
            return data["runs"]
    except ValueError:
        pass
    runs = []
    for line in text.splitlines():
        try:
            run = json.loads(line)
        except ValueError:
            continue
        if isinstance(run, dict):
            runs.append(run)
    return runs


def _is_treated(cfg: Config, rule: TryRule, arm) -> bool:
    if rule.treated_prefix:
        return (
            isinstance(arm, str)
            and arm.startswith(rule.treated_prefix)
            and arm != cfg.baseline.arm
            and arm not in rule.treated_exclude
        )
    return arm == cfg.treated.arm


def _treated_key(cfg: Config, rule: TryRule) -> str:
    return rule.treated_prefix or cfg.treated.arm


def _tally(cfg: Config, rule: TryRule, runs: list, task_id: str):
    """`({arm key: (passes, runs)}, {arm key: mean calls})` for one task, or None if a side is empty."""
    mine = [r for r in runs if r.get("task_id") == task_id]
    sides = {
        cfg.baseline.arm: [r for r in mine if r.get("arm") == cfg.baseline.arm],
        _treated_key(cfg, rule): [r for r in mine if _is_treated(cfg, rule, r.get("arm"))],
    }
    if any(not rows for rows in sides.values()):
        return None
    counts = {k: (sum(1 for r in rows if r.get("passed")), len(rows)) for k, rows in sides.items()}
    calls = {}
    for k, rows in sides.items():
        values = [r["tool_calls"] for r in rows if isinstance(r.get("tool_calls"), (int, float))]
        if values:
            calls[k] = sum(values) / len(values)
    return counts, calls


def _history_before(cfg: Config, rule: TryRule, task_id: str):
    """The comparison to beat for a task outside the full holdout: the newest earlier file that ran
    both sides of it."""
    if not rule.before_glob:
        return None
    for path in sorted(cfg.results_dir.glob(rule.before_glob), reverse=True):
        got = _tally(cfg, rule, _read_runs(path), task_id)
        if got:
            return got
    return None


def _calls_label(before: float, after: float) -> Optional[str]:
    if before <= 0:
        return None
    if after <= before * (1 - CALLS_BAND) + 1e-9:
        return "cheaper"
    if after >= before * (1 + CALLS_BAND) - 1e-9:
        return "costlier"
    return None


def _fmt(n: float) -> str:
    return f"${n:.2f}"


def run_try(args, cfg, nightly, validator, container_running, runner, confirm, who, git_state, out, now) -> int:
    status = build_status(cfg, now=now, nightly=nightly)
    history = None
    if args.task_id:
        task_id = args.task_id
        named = next((r for r in cfg.tries if r.tasks is not None and task_id in r.tasks and r.before_glob), None)
        if named is not None:
            history = _history_before(cfg, named, task_id)
            if history is None:
                out(f"There is no earlier run of {task_id} with both sides, so there is nothing to compare a re-run to.")
                return 2
        elif status.measured_at is None:
            out("No full holdout run found in the results directory, so there is nothing to compare a re-run to.")
            return 2
        elif task_id not in status.outcomes:
            out(f"{task_id} is not in the last holdout ({status.measured_at[:10]}).")
            return 2
    elif status.measured_at is None:
        out("No full holdout run found in the results directory, so there is nothing to compare a re-run to.")
        return 2
    elif status.worklist:
        task_id = status.worklist[0].task_id
    else:
        out(f"Nothing is failing in the last holdout ({status.measured_at[:10]}), so there is nothing to try.")
        return 0

    rule = try_rule_for(cfg, task_id)
    if rule is None:
        out(f"The adapter has no [[try]] rule for {task_id}, so improve does not know how to re-run it.")
        return 2

    # Free checks first: never pay to run a task that is itself broken.
    vrule = rule_for(cfg, task_id)
    validation, _ = _validate_cached(cfg, task_id, vrule, validator, container_running)
    if validation is None:
        out(f"{task_id} needs {vrule.container} to check the task, and it is not running.")
        if vrule.start_hint:
            out(f"Start it with: {vrule.start_hint}")
        return 3
    if not validation.ok:
        out(f"The task is broken: {validation.detail}")
        out("Fix the task before spending anything on it.")
        return 1

    events = read_ledger(cfg)
    held = open_iteration(events, task_id)
    if held and held.get("who") != who:
        out(f"{held['id']} on {task_id} is held by {held.get('who')} (taken {str(held.get('ts', ''))[:10]}).")
        out("One holder per item. They can finish it, or you can pick another task.")
        return 6

    spent_week = spend_this_week(events, now)
    left = max(cfg.per_week_usd - spent_week, 0.0)
    if left <= 0:
        out(f"The weekly budget is spent ({_fmt(spent_week)} of {_fmt(cfg.per_week_usd)}). Nothing runs until next week.")
        return 5
    cap = args.cap if args.cap is not None else cfg.per_try_usd
    capped_by_week = cap > left
    cap = min(cap, left)
    subject = getattr(args, "subject", None)
    # 135: the programme budget bounds a try as well, overall and for the subject it is tagged with.
    programme_left = []
    if cfg.total_usd:
        programme_left.append(cfg.total_usd - programme_spend(cfg, events))
    if cfg.per_subject_usd and subject:
        programme_left.append(cfg.per_subject_usd - programme_spend(cfg, events, subject))
    if programme_left:
        if min(programme_left) <= 0:
            out("The programme budget is spent for this subject or overall. Nothing runs.")
            return 5
        cap = min(cap, min(programme_left))
    repeats = args.repeats or rule.repeats
    imp_id = held["id"] if held else next_imp_id(events)
    record_path = cfg.results_dir / f"try-{imp_id}.json"

    def fill(command):
        values = {"task": task_id, "repeats": str(repeats), "cap": str(float(cap)), "out": str(record_path)}
        return [part.format(**values) if "{" in part else part for part in command]

    env = {**os.environ, **rule.env}
    estimate = runner([*fill(rule.command), rule.dry_run_flag], env, 120, live=False)
    out(f"{imp_id}: re-run {task_id}, {repeats} repeats")
    out("")
    out(estimate.stdout.strip())
    if rule.estimate_note:
        out(rule.estimate_note)
    out("")
    if capped_by_week:
        out(f"Weekly budget: {_fmt(spent_week)} of {_fmt(cfg.per_week_usd)} spent, {_fmt(left)} left, so the cap is {_fmt(cap)}.")
    else:
        out(f"Weekly budget: {_fmt(spent_week)} of {_fmt(cfg.per_week_usd)} spent.")
    out(f"Spend cap of {_fmt(cap)}: no session starts once measured spend reaches it (the last one can overshoot).")
    if not args.yes and not confirm(f"Run {task_id} now? [y/N] "):
        out("Not run. Nothing was spent and nothing was written.")
        return 0

    commit, dirty = git_state()
    started = time.monotonic()

    def stamp() -> str:
        """The injected clock plus the time the run has taken, so a test's clock is the ledger's clock
        and the week a cost lands in is the week the spending began."""
        return (now + timedelta(seconds=time.monotonic() - started)).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not held:
        append_ledger(cfg, {"ts": stamp(), "id": imp_id, "event": "claim", "who": who, "task": task_id})
    result = runner(fill(rule.command), env, rule.timeout_seconds, live=True)
    costs = re.findall(rule.cost_regex, result.stdout) if rule.cost_regex else []
    cost = sum(float(c) for c in costs)
    record = None
    if record_path.exists():
        try:
            record = json.loads(record_path.read_text())
        except ValueError:
            record = None
    aborted = result.returncode != 0 or record is None
    applied = None
    if rule.applied_field and record is not None:
        treated_rows = [r for r in record["runs"] if r.get("task_id") == task_id and _is_treated(cfg, rule, r.get("arm"))]
        yes = sum(1 for r in treated_rows if r.get(rule.applied_field) is True)
        no = sum(1 for r in treated_rows if r.get(rule.applied_field) is False)
        applied = {"yes": yes, "no": no, "unknown": len(treated_rows) - yes - no}
    criteria_sha = _criteria_sha256(cfg)
    append_ledger(cfg, {
        "ts": stamp(), "id": imp_id, "event": "run", "who": who, "task": task_id,
        "cost_usd": round(cost, 4), "sessions": len(costs), "returncode": result.returncode,
        "aborted": aborted, "cap": float(cap), "repeats": repeats,
        "commit": commit, "dirty": dirty,
        "record": os.path.relpath(record_path, cfg.root),
        **({"applied": applied} if applied is not None else {}),
        **({"subject": subject} if subject else {}),
        **({"criteria_sha256": criteria_sha} if criteria_sha else {}),
    })

    out("")
    if aborted:
        append_ledger(cfg, {"ts": stamp(), "id": imp_id, "event": "verdict", "task": task_id, "label": "incomplete"})
        out(f"The run did not finish (exit {result.returncode}). {_fmt(cost)} was spent over {len(costs)} sessions and is in the ledger.")
        out("There is no result to judge. A partial run is not a verdict.")
        return 7

    tkey = _treated_key(cfg, rule)
    arms = {cfg.baseline.arm: cfg.baseline.label, tkey: cfg.treated.label}
    calls_before: dict = {}
    if history is not None:
        before, calls_before = history
    else:
        before = {
            cfg.baseline.arm: (status.outcomes[task_id]["baseline"]["passes"], status.outcomes[task_id]["baseline"]["runs"]),
            tkey: (status.outcomes[task_id]["treated"]["passes"], status.outcomes[task_id]["treated"]["runs"]),
        }
    tally = _tally(cfg, rule, record["runs"], task_id)
    if tally is None:
        append_ledger(cfg, {"ts": stamp(), "id": imp_id, "event": "verdict", "task": task_id, "label": "incomplete"})
        out("The run record has no sessions for one of the arms, so there is nothing to compare.")
        return 7
    after, calls_after = tally
    label = judge(before, after)
    calls, relative = {}, {}
    if rule.judge_calls and tkey in calls_before and tkey in calls_after:
        calls = {tkey: [round(calls_before[tkey], 1), round(calls_after[tkey], 1)]}
        compare = (calls_before[tkey], calls_after[tkey])
        base = cfg.baseline.arm
        # Judged against the baseline arm of the same run, so a change that made every arm cheaper
        # (a better tool, a faster model) is not credited to the treatment.
        if calls_before.get(base) and calls_after.get(base):
            compare = (calls_before[tkey] / calls_before[base], calls_after[tkey] / calls_after[base])
            relative = {tkey: [round(compare[0], 2), round(compare[1], 2)]}
        if label == "no change":
            label = _calls_label(*compare) or label
    append_ledger(cfg, {
        "ts": stamp(), "id": imp_id, "event": "verdict", "task": task_id, "label": label,
        "before": {a: list(v) for a, v in before.items()}, "after": {a: list(v) for a, v in after.items()},
        **({"calls": calls} if calls else {}),
        **({"relative_calls": relative} if relative else {}),
        "record": os.path.relpath(record_path, cfg.root),
    })
    out(f"{imp_id}  {task_id}")
    for arm, name in arms.items():
        out(f"  {name:<18}was {before[arm][0]}/{before[arm][1]} passed, now {after[arm][0]}/{after[arm][1]}")
    if calls:
        out(f"  {'calls per session':<18}was {calls[tkey][0]:g}, now {calls[tkey][1]:g}")
        if relative:
            out(f"  {'against baseline':<18}was {relative[tkey][0]:.1f}x the baseline, now {relative[tkey][1]:.1f}x")
    unused = False
    if applied is not None:
        total = applied["yes"] + applied["no"] + applied["unknown"]
        out(f"  {rule.applied_label or rule.applied_field} in {applied['yes']} of {total} treated sessions")
        unused = total > 0 and applied["yes"] == 0
    out("")
    state = "uncommitted changes in the tree" if dirty else "clean tree"
    out(f"Run on commit {commit[:7]} ({state}).")
    note = " Differences smaller than half the repeats are within noise at this size." if label == "no change" else ""
    out(f"Verdict: {label}. Three repeats show a direction, not proof.{note}")
    out(f"Spent {_fmt(cost)} of the {_fmt(cap)} cap; this week {_fmt(spent_week + cost)} of {_fmt(cfg.per_week_usd)}.")
    if label in ("fixed", "better", "cheaper") and unused:
        out("No treated session applied the treatment, so this result measures the arm's name, not the treatment. Nothing to cite.")
    elif label in ("fixed", "better", "cheaper"):
        out(f"To keep the change, commit it with the trailer:  Improve: {imp_id}")
    elif label == "no change":
        out("Nothing improved, so there is nothing to cite.")
    else:
        out("To undo the change, revert it; nothing else needs cleaning up.")
    return 0


# ---- 135: the programme budget, `measure` and `report` -------------------------------------------


def programme_spend(cfg: Config, events: list, subject: Optional[str] = None) -> float:
    """Measured dollars in the ledger from `budget_since` on, for one subject or all of them."""
    total = 0.0
    for event in events:
        if event.get("event") not in ("run", "measure"):
            continue
        if cfg.budget_since and str(event.get("ts", "")) < cfg.budget_since:
            continue
        if subject is not None and event.get("subject") != subject:
            continue
        total += float(event.get("cost_usd") or 0)
    return total


def _criteria_sha256(cfg: Config) -> Optional[str]:
    """The criteria file's sha256; None when the adapter names none or it cannot be read."""
    if not cfg.criteria:
        return None
    try:
        return hashlib.sha256(Path(cfg.criteria).read_bytes()).hexdigest()
    except OSError:
        return None


def _checkpoint(cfg: Config, before: float, after: float) -> Optional[int]:
    """The $N mark crossed between two programme totals, if any."""
    if cfg.checkpoint_usd <= 0:
        return None
    mark = int(after // cfg.checkpoint_usd)
    return int(mark * cfg.checkpoint_usd) if mark > int(before // cfg.checkpoint_usd) else None


def run_measure(args, cfg, runner, confirm, who, git_state, out, now) -> int:
    if not cfg.measures:
        out("The adapter has no [[measure]] rule, so improve does not know how to run a subject.")
        return 2
    subject = args.subject
    rule = (next((r for r in cfg.measures if subject in r.subjects), None)
            or next((r for r in cfg.measures if not r.subjects), cfg.measures[0]))
    side = "holdout" if args.purpose == "verdict" else "train"
    events = read_ledger(cfg)
    spent_total = programme_spend(cfg, events)
    spent_subject = programme_spend(cfg, events, subject)
    limits = []
    if cfg.total_usd:
        limits.append(("overall", cfg.total_usd - spent_total))
    if cfg.per_subject_usd:
        limits.append((subject, cfg.per_subject_usd - spent_subject))
    ask = args.cap if args.cap is not None else (cfg.per_measure_usd or cfg.per_try_usd)
    cap = min([ask] + [left for _, left in limits])
    if cap <= 0:
        for name, left in limits:
            if left <= 0:
                out(f"The budget for {name} is spent ({_fmt(spent_subject if name == subject else spent_total)}). Nothing runs.")
        return 5
    repeats = args.repeats or rule.repeats

    def fill(command):
        values = {"subject": subject, "side": side, "repeats": str(repeats), "cap": str(float(cap)),
                  "spent": "0.0"}
        filled = [part.format(**values) if "{" in part else part for part in command]
        return filled + (list(rule.verdict_args) if args.purpose == "verdict" else []) + list(args.arg or [])

    env = {**os.environ, **rule.env}
    imp_id = next_imp_id(events)
    estimate = runner([*fill(rule.command), rule.dry_run_flag], env, 120, live=False)
    out(f"{imp_id}: {args.purpose} run of {subject} on the {side} side, {repeats} repeats")
    out("")
    out(estimate.stdout.strip())
    if rule.estimate_note:
        out(rule.estimate_note)
    out("")
    for name, left in limits:
        if name == subject:
            out(f"{_fmt(left)} left for {subject} ({_fmt(cfg.per_subject_usd)} budget).")
        else:
            out(f"{_fmt(left)} left overall ({_fmt(cfg.total_usd)} budget).")
    out(f"Spend cap of {_fmt(cap)}: no session starts once measured spend reaches it (the last one can overshoot).")
    if not args.yes and not confirm(f"Run {subject} now? [y/N] "):
        out("Not run. Nothing was spent and nothing was written.")
        return 0

    commit, dirty = git_state()
    # Reserved before the harness starts, so a second run started meanwhile reads a ledger that
    # already holds this id and takes the next one. Read again here: the id taken at the top is
    # from before the estimate and the question.
    imp_id = next_imp_id(read_ledger(cfg))
    append_ledger(cfg, {"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "id": imp_id, "event": "claim",
                        "who": who, "subject": subject})
    extra = {"cwd": args.cwd} if args.cwd else {}
    result = runner(fill(rule.command), env, rule.timeout_seconds, live=True, **extra)
    costs = re.findall(rule.cost_regex, result.stdout)
    cost = sum(float(c) for c in costs)
    found = re.findall(rule.runs_file_regex, result.stdout)
    runs_file = None
    if found:
        path = Path(found[-1])
        # Resolved, so a file written through a symlink from another checkout is recorded where it lives.
        runs_file = os.path.relpath(path.resolve(), cfg.root.resolve()) if path.is_absolute() else found[-1]
    aborted = result.returncode != 0 or runs_file is None
    event = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "id": imp_id, "event": "measure", "who": who,
        "subject": subject, "side": side, "purpose": args.purpose, "runs_file": runs_file,
        "cost_usd": round(cost, 4), "sessions": len(costs), "returncode": result.returncode,
        "aborted": aborted, "cap": float(cap), "repeats": repeats, "commit": commit, "dirty": dirty,
        **({"continues": args.continues} if args.continues else {}),
    }
    criteria_sha = _criteria_sha256(cfg)
    if criteria_sha:
        event["criteria_sha256"] = criteria_sha
    append_ledger(cfg, event)

    new_total, new_subject = spent_total + cost, spent_subject + cost
    out("")
    out(f"{imp_id}: {_fmt(cost)} this run over {len(costs)} sessions"
        + (" (the run did not finish)" if aborted else "") + ".")
    out(f"Spend: {_fmt(new_subject)} of {_fmt(cfg.per_subject_usd)} for {subject}; "
        f"{_fmt(new_total)} of {_fmt(cfg.total_usd)} overall.")
    mark = _checkpoint(cfg, spent_total, new_total)
    if mark is not None:
        out(f"CHECKPOINT: the programme crossed ${mark}. Stop and report before the next run.")
    if aborted:
        out("Aborted runs are recorded with their spend; `improve report` gives no verdict from them alone.")
        return 7
    out("Next: improve report")
    return 8 if mark is not None else 0


def run_report(cfg, runner, out) -> int:
    if not cfg.report_command:
        out("The adapter has no [report] command, so improve does not know how to read a verdict.")
        return 2
    argv = [*cfg.report_command, "--ledger", str(cfg.ledger), "--criteria", cfg.criteria,
            "--root", str(cfg.root)]
    result = runner(argv, {**os.environ}, 600, live=False)
    out(result.stdout.rstrip())
    return result.returncode


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


def _make_git_state(cfg: Config) -> Callable[[], tuple]:
    def state() -> tuple:
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cfg.root, capture_output=True,
                                 text=True, timeout=30, check=False).stdout.strip() or "unknown"
            dirty = bool(subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                                        cwd=cfg.root, capture_output=True, text=True, timeout=30,
                                        check=False).stdout.strip())
        except (OSError, subprocess.SubprocessError):
            return "unknown", False
        return sha, dirty
    return state


def _stream_runner(argv, env, timeout, live=False, cwd=None) -> RunResult:
    """Run a command. With `live`, show its output as it arrives: a re-run can take minutes."""
    proc = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cwd)
    lines = []
    try:
        for line in proc.stdout:
            if live:
                sys.stdout.write(line)
                sys.stdout.flush()
            lines.append(line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        lines.append("improve: timed out\n")
    return RunResult(proc.returncode if proc.returncode is not None else 1, "".join(lines))


def _aliases_from_adapter() -> dict:
    try:
        return dict(tomllib.loads(find_adapter().read_text()).get("alias", {}))
    except (ConfigError, OSError, ValueError):
        return {}


def _ask(prompt: str) -> bool:
    if not sys.stdin.isatty():
        return False  # no terminal and no --yes: not a yes
    return input(prompt).strip().lower() in ("y", "yes")


# ---- entry point -------------------------------------------------------------------------------


def main(
    argv=None,
    *,
    config: Optional[Config] = None,
    nightly: Optional[Callable[[], Nightly]] = None,
    validator: Optional[Callable[[str], Validation]] = None,
    container_running: Optional[Callable[[str], bool]] = None,
    runner: Optional[Callable] = None,
    confirm: Optional[Callable[[str], bool]] = None,
    who: Optional[str] = None,
    git_state: Optional[Callable[[], tuple]] = None,
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
    p_try = sub.add_parser("try", help="re-run one task after a change and say whether it helped (spends)")
    p_try.add_argument("task_id", nargs="?", help="the task; default is the top of the worklist")
    p_try.add_argument("--yes", action="store_true", help="skip the question (the estimate and cap are still shown)")
    p_try.add_argument("--cap", type=float, default=None, help="dollars; default is the adapter's per-try cap")
    p_try.add_argument("--repeats", type=int, default=None, help="repeats per arm; default is the adapter's")
    p_try.add_argument("--subject", default=None, help="charge the spend to this subject's budget")
    p_measure = sub.add_parser(
        "measure", help="run the harness for one subject and record it in the ledger (spends)"
    )
    p_measure.add_argument("subject")
    p_measure.add_argument("--purpose", choices=("verdict", "train"), default="verdict",
                           help="verdict = the subject's held-out tasks; train = its train tasks")
    p_measure.add_argument("--yes", action="store_true", help="skip the question (estimate and cap still shown)")
    p_measure.add_argument("--cap", type=float, default=None)
    p_measure.add_argument("--repeats", type=int, default=None)
    p_measure.add_argument("--continues", default=None, metavar="IMP-NNNN",
                           help="this run finishes the sessions a capped run did not reach")
    p_measure.add_argument("--cwd", default=None,
                           help="run the harness command from this directory (an earlier checkout)")
    p_measure.add_argument("--arg", action="append", default=None,
                           help="an extra argument for the harness command (repeatable, use --arg=--flag)")
    sub.add_parser("report", help="the verdict per subject against the adapter's criteria (free)")
    argv = list(sys.argv[1:] if argv is None else argv)
    # The adapter may give a verb another name (`[alias] <word> = "report"`), so a project can speak
    # its own words while the engine stays generic. Read before argparse, from the adapter alone.
    aliases = (config.aliases if config else _aliases_from_adapter())
    if argv and argv[0] in aliases:
        argv[0] = aliases[argv[0]]
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
    if args.verb == "report":
        return run_report(cfg, runner or _stream_runner, out)
    holder = who or os.environ.get("IMPROVE_WHO") or os.environ.get("USER") or "unknown"
    if args.verb == "measure":
        return run_measure(args, cfg, runner or _stream_runner, confirm or _ask, holder,
                           git_state or _make_git_state(cfg), out, now)
    if args.verb == "try":
        return run_try(args, cfg, nightly, validator, container_running, runner or _stream_runner,
                       confirm or _ask, holder, git_state or _make_git_state(cfg), out, now)
    return run_next(args, cfg, nightly, validator, container_running, out, now)


if __name__ == "__main__":
    sys.exit(main())
