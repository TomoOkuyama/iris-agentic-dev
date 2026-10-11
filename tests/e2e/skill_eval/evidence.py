"""The per-skill verdict against specs/135-skill-evidence/criteria.md (`improve skills`).

135 T002. Everything here is derived from run files (`ladder-*.runs.jsonl`) and the ledger's
`measure` events. Nothing is stored. The numbers in `criteria.md` are the numbers in this file; a test
fails when either moves alone.

A *run* is one invocation of the ladder for one skill: arms `tools` and `tools+<skill>`, the skill's
held-out tasks, three repeats. A *pair* is the same task and repeat in both arms. A pair is *usable*
when both sessions were scored and the treated session loaded the skill.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from collections import defaultdict

SEED = 135
RESAMPLES = 10000

MIN_TASKS = 5
MIN_PAIRS_PER_TASK = 2
MIN_REPEATS = 3
MIN_LOADED_RATE = 0.90

COMPLETION_MARGIN = 3
COMPLETION_MAX_LOSSES = 1
CALLS_RATIO_MAX = 0.75
COST_RATIO_MAX = 0.80
SHARE_CHEAPER_MIN = 0.75
QUALITY_MARGIN = 0.15

KIND_OF = {"2a": "completion", "2b": "efficiency", "2c": "quality"}
KINDS = ("2a", "2b", "2c")


# --- small numerics ---------------------------------------------------------------------------------


def sha256_file(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def criteria_intact(path: str, events: list) -> bool:
    """True when the criteria file still hashes to the value every 135 run event recorded."""
    recorded = {e["criteria_sha256"] for e in events if e.get("criteria_sha256")}
    if not recorded:
        return True
    return recorded == {sha256_file(path)}


def bootstrap_interval(
    items, statistic, *, resamples: int = RESAMPLES, seed: int = SEED
):
    """95 percent percentile interval, resampling `items` (one per task) with replacement."""
    items = list(items)
    if not items:
        return (None, None)
    rng = random.Random(seed)
    n = len(items)
    values = sorted(
        statistic([items[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples)
    )
    return (values[int(0.025 * resamples)], values[int(0.975 * resamples) - 1])


def _mean(xs):
    return sum(xs) / len(xs)


def _ratio(pairs):
    """pairs: (treated_sum, tools_sum) per task."""
    tools = sum(t for _, t in pairs)
    return sum(s for s, _ in pairs) / tools if tools else float("nan")


# --- one run ------------------------------------------------------------------------------------------


def _index(lines, arm):
    # A later line replaces an earlier one.
    return {
        (line["task_id"], line["run_index"]): line
        for line in lines
        if line.get("arm") == arm
    }


def _wins(pairs):
    """(b, c): pairs only the treated arm passed, and pairs only the tools arm passed."""
    b = sum(1 for t, s in pairs if s["passed"] and not t["passed"])
    c = sum(1 for t, s in pairs if t["passed"] and not s["passed"])
    return b, c


def _tokens(lines):
    total = defaultdict(int)
    for line in lines:
        for key, value in (line.get("tokens") or {}).items():
            if isinstance(value, int):
                total[key] += value
    return dict(total)


def _analyse(lines, skill, heldout, *, check_repeats):
    """Counts, means and intervals for one set of session lines. No verdict wording here."""
    treated_arm = f"tools+{skill}"
    lines = [line for line in lines if line.get("arm") in ("tools", treated_arm)]
    tasks_seen = sorted({line["task_id"] for line in lines})
    excluded = sorted(set(tasks_seen) - set(heldout)) if heldout is not None else []
    if heldout is not None:
        lines = [line for line in lines if line["task_id"] in heldout]

    tools, treated = _index(lines, "tools"), _index(lines, treated_arm)
    keys = sorted(set(tools) & set(treated))

    loaded_flags = [
        s.get("skill_loaded")
        for s in treated.values()
        if s.get("skill_loaded") is not None
    ]
    loaded_rate = (
        (sum(1 for f in loaded_flags if f) / len(loaded_flags))
        if loaded_flags
        else None
    )

    usable_by_task = defaultdict(list)
    unloaded = unscored = 0
    for key in keys:
        t, s = tools[key], treated[key]
        if s.get("skill_loaded") is False:
            unloaded += 1
        elif t.get("passed") is None or s.get("passed") is None:
            unscored += 1
        else:
            usable_by_task[key[0]].append((t, s))

    eligible = sorted(
        task
        for task, pairs in usable_by_task.items()
        if len(pairs) >= MIN_PAIRS_PER_TASK
    )
    thin = {
        task: len(pairs)
        for task, pairs in usable_by_task.items()
        if len(pairs) < MIN_PAIRS_PER_TASK
    }
    pairs = [pair for task in eligible for pair in usable_by_task[task]]

    b, c = _wins(pairs)

    per_task = {}
    for task in eligible:
        group = usable_by_task[task]
        task_b, task_c = _wins(group)
        costed = _has_cost(group)
        per_task[task] = {
            "pairs": len(group),
            "b": task_b,
            "c": task_c,
            "calls_t": sum(t.get("tool_calls") or 0 for t, _ in group),
            "calls_s": sum(s.get("tool_calls") or 0 for _, s in group),
            "cost_t": sum(t["cost_usd"] for t, _ in group) if costed else None,
            "cost_s": sum(s["cost_usd"] for _, s in group) if costed else None,
            "quality": _task_quality(group),
        }

    result = {
        "skill": skill,
        "tasks": eligible,
        "thin_tasks": thin,
        "excluded_tasks": excluded,
        "pairs": len(pairs),
        "unloaded": unloaded,
        "unscored": unscored,
        "loaded_rate": loaded_rate,
        "repeats": len({line["run_index"] for line in lines}),
        "b": b,
        "c": c,
        "per_task": per_task,
        "tokens": {
            "tools": _tokens([t for t, _ in pairs]),
            "treated": _tokens([s for _, s in pairs]),
        },
        "tools_passes": sum(1 for t, _ in pairs if t["passed"]),
        "treated_passes": sum(1 for _, s in pairs if s["passed"]),
        "timeouts": sum(
            1 for t, s in pairs if t.get("timed_out") or s.get("timed_out")
        ),
        "check_repeats": check_repeats,
    }
    result.update(_criteria(result, eligible, per_task))
    return result


def _has_cost(group):
    return all(
        t.get("cost_usd") is not None and s.get("cost_usd") is not None
        for t, s in group
    )


def _task_quality(group):
    both = [
        (t["quality"], s["quality"])
        for t, s in group
        if t.get("quality") is not None and s.get("quality") is not None
    ]
    if not both:
        return None
    return {
        "tools": _mean([a for a, _ in both]),
        "treated": _mean([b for _, b in both]),
        "n": len(both),
    }


def _criteria(result, eligible, per_task):
    b, c = result["b"], result["c"]
    criteria = {"1": b >= c}
    criteria["2a"] = (b - c) >= COMPLETION_MARGIN and c <= COMPLETION_MAX_LOSSES

    out = {"calls_ratio": None, "cost_ratio": None}
    tasks = [per_task[t] for t in eligible]
    costed = bool(tasks) and all(t["cost_t"] is not None for t in tasks)

    criteria["2b"] = False
    if tasks:
        calls_items = [(t["calls_s"], t["calls_t"]) for t in tasks]
        out["calls_ratio"] = _ratio(calls_items)
        out["calls_ratio_ci"] = bootstrap_interval(calls_items, _ratio)
        calls_diff = [(t["calls_s"] - t["calls_t"]) / t["pairs"] for t in tasks]
        out["calls_diff"] = _mean(calls_diff)
        out["calls_diff_ci"] = bootstrap_interval(calls_diff, _mean)
    if costed:
        cost_items = [(t["cost_s"], t["cost_t"]) for t in tasks]
        out["cost_ratio"] = _ratio(cost_items)
        out["cost_ratio_ci"] = bootstrap_interval(cost_items, _ratio)
        cost_diff = [(t["cost_s"] - t["cost_t"]) / t["pairs"] for t in tasks]
        out["cost_diff"] = _mean(cost_diff)
        out["cost_diff_ci"] = bootstrap_interval(cost_diff, _mean)
        out["share_cheaper"] = sum(1 for t in tasks if t["cost_s"] < t["cost_t"]) / len(
            tasks
        )
        criteria["2b"] = bool(
            out["calls_ratio"] <= CALLS_RATIO_MAX
            and out["cost_ratio"] <= COST_RATIO_MAX
            and out["share_cheaper"] >= SHARE_CHEAPER_MIN
            and out["calls_diff_ci"][1] is not None
            and out["calls_diff_ci"][1] < 0
            and out["cost_diff_ci"][1] < 0
        )

    quality_ok = bool(tasks) and all(t["quality"] is not None for t in tasks)
    criteria["2c"] = False
    out["quality_available"] = quality_ok
    if quality_ok:
        diff = [t["quality"]["treated"] - t["quality"]["tools"] for t in tasks]
        out["quality_diff"] = _mean(diff)
        out["quality_diff_ci"] = bootstrap_interval(diff, _mean)
        criteria["2c"] = bool(
            out["quality_diff"] >= QUALITY_MARGIN
            and out["quality_diff_ci"][0] > 0
            and result["treated_passes"] >= result["tools_passes"]
        )

    criteria["2"] = any(criteria[k] for k in KINDS)
    out["criteria"] = criteria
    out["kinds"] = [KIND_OF[k] for k in KINDS if criteria[k]]
    return out


def _models(lines):
    """The distinct (model, effort) pairs in a set of lines. Lines from before 135 name none."""
    return {(line.get("model"), line.get("effort")) for line in lines}


def _ineligible(result, lines):
    """Why this run gets no verdict, or None."""
    stamped = [
        line
        for line in lines
        if line.get("arm") in ("tools", f"tools+{result['skill']}")
    ]
    if any(not line.get("build") for line in stamped):
        return "legacy run: session lines carry no build stamp, so the binary and commit are unknown"
    builds = {
        (line["build"].get("binary_sha256"), line["build"].get("commit"))
        for line in stamped
    }
    if len(builds) > 1:
        return "the run's sessions name more than one binary or commit"
    if len(_models(stamped)) > 1:
        return "the run's sessions name more than one model or effort"
    if any(line["build"].get("binary_stale") for line in stamped):
        return "the run used a binary older than the source"
    if any(line["build"].get("dirty") for line in stamped):
        return "the run started with uncommitted changes to tracked files"
    if result["check_repeats"] and result["repeats"] < MIN_REPEATS:
        return f"fewer than {MIN_REPEATS} repeats ({result['repeats']})"
    rate = result["loaded_rate"]
    if rate is None or rate < MIN_LOADED_RATE:
        shown = "none" if rate is None else f"{rate:.0%}"
        return f"the skill was loaded in {shown} of treated sessions, under {MIN_LOADED_RATE:.0%}"
    if len(result["tasks"]) < MIN_TASKS:
        return (
            f"fewer than {MIN_TASKS} held-out tasks with {MIN_PAIRS_PER_TASK} usable pairs "
            f"({len(result['tasks'])})"
        )
    return None


def evaluate_run(lines, skill, heldout=None) -> dict:
    """One run's counts, intervals and, when it is eligible, whether criteria 1 and 2 hold."""
    result = _analyse(lines, skill, heldout, check_repeats=True)
    why = _ineligible(result, lines)
    result["ineligible"] = why
    if why:
        result["verdict"] = f"no verdict ({why})"
    elif not (result["criteria"]["1"] and result["criteria"]["2"]):
        result["verdict"] = "not net positive"
    else:
        result["verdict"] = "first run qualifies, awaiting replication"
    return result


# --- replication ----------------------------------------------------------------------------------------


def _later_points_the_same_way(kind, result):
    if kind == "2a":
        return result["b"] > result["c"]
    if kind == "2b":
        return bool(
            result.get("calls_ratio") is not None
            and result["calls_ratio"] < 1
            and result.get("cost_ratio") is not None
            and result["cost_ratio"] < 1
            and result.get("cost_diff") is not None
            and result["cost_diff"] < 0
        )
    return bool(result.get("quality_diff") is not None and result["quality_diff"] > 0)


def _direction_agrees(kind, first, later):
    """Every task that decided the first run points the same way in the later runs."""
    deciding, agree = 0, 0
    for task, one in first["per_task"].items():
        other = later["per_task"].get(task)
        if kind == "2a":
            d1 = one["b"] - one["c"]
            if one["b"] == 0 and one["c"] == 0:
                continue
            deciding += 1
            d2 = (other["b"] - other["c"]) if other else 0
            agree += 1 if (d1 > 0 and d2 > 0) or (d1 < 0 and d2 < 0) else 0
        elif kind == "2b":
            deciding += 1
            ok = bool(
                other
                and other["cost_t"] is not None
                and other["cost_s"] < other["cost_t"]
                and other["calls_s"] < other["calls_t"]
            )
            agree += 1 if ok else 0
        else:
            deciding += 1
            q = other["quality"] if other else None
            agree += 1 if q and q["treated"] > q["tools"] else 0
    return deciding > 0 and agree == deciding


def evaluate_skill(runs, skill, heldout=None) -> dict:
    """Criterion 3 over the skill's verdict runs, in the order they were taken."""
    if not runs:
        return {"verdict": "no verdict (no held-out run yet)", "runs": []}
    singles = [evaluate_run(lines, skill, heldout) for lines in runs]
    first = singles[0]
    out = {"runs": singles, "kinds": [], "replication": None, "pooled": None}
    if first["ineligible"]:
        out["verdict"] = first["verdict"]
        return out
    if not (first["criteria"]["1"] and first["criteria"]["2"]):
        out["verdict"] = "not net positive"
        return out
    if len(singles) == 1:
        out["verdict"] = first["verdict"]
        out["kinds"] = first["kinds"]
        return out

    if len(_models([line for lines in runs for line in lines])) > 1:
        out["verdict"] = "no verdict (the runs name more than one model or effort, so one cannot replicate the other)"
        return out

    later = singles[1:]
    for index, one in enumerate(later, start=2):
        if one["ineligible"]:
            out["verdict"] = (
                f"no verdict (replication run {index}: {one['ineligible']})"
            )
            return out

    # Pooled data: every later run joins the first, and repeat numbers are made unique per run so a
    # repeat 0 of run 2 is not read as a second look at repeat 0 of run 1.
    pooled_lines = []
    for number, lines in enumerate(runs):
        for line in lines:
            pooled_lines.append(
                {**line, "run_index": number * 1000 + line["run_index"]}
            )
    pooled = _analyse(pooled_lines, skill, heldout, check_repeats=False)
    out["pooled"] = pooled

    later_lines = [line for lines in runs[1:] for line in lines]
    later_pooled = _analyse(
        [{**line, "run_index": i} for i, line in enumerate(later_lines)],
        skill,
        heldout,
        check_repeats=False,
    )
    each_not_worse = all(one["criteria"]["1"] for one in later)
    held = {"pooled": False, "direction": False, "kinds": []}
    for key in KINDS:
        if not first["criteria"][key]:
            continue
        pooled_ok = (
            pooled["criteria"]["1"]
            and pooled["criteria"][key]
            and all(_later_points_the_same_way(key, one) for one in later)
        )
        direction_ok = _direction_agrees(key, first, later_pooled)
        held["pooled"] = held["pooled"] or bool(pooled_ok)
        held["direction"] = held["direction"] or bool(direction_ok)
        if pooled_ok or direction_ok:
            held["kinds"].append(KIND_OF[key])
    out["replication"] = held
    if each_not_worse and held["kinds"]:
        out["verdict"] = "net positive"
        out["kinds"] = held["kinds"]
    else:
        out["verdict"] = "not net positive"
    return out


# --- from the ledger and files --------------------------------------------------------------------------


def _read_lines(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _fingerprints(lines):
    return {
        line["task_id"]: line.get("task_fingerprint")
        for line in lines
        if line.get("task_fingerprint")
    }


def _subject(event):
    """The ledger names the thing measured `subject`; here it is a skill."""
    return event.get("subject") or event.get("skill")


def skills_report(events, *, criteria_path, heldout, task_skill=None, root=".") -> dict:
    """Per-skill rows from the ledger's `measure` events and the run files they name."""
    measures = [e for e in events if e.get("event") == "measure"]
    report = {"refused": None, "skills": {}, "criteria_sha256": None}
    if not criteria_intact(criteria_path, measures):
        report["refused"] = (
            f"{criteria_path} changed after the first 135 run event recorded its hash, so no verdict "
            "is given. A changed criterion is a new study with new runs"
        )
    skills = sorted(set(heldout) | {_subject(e) for e in measures if _subject(e)})
    for skill in skills:
        mine = sorted(
            (e for e in measures if _subject(e) == skill), key=lambda e: e["ts"]
        )
        verdict_events = [e for e in mine if e.get("purpose") == "verdict"]
        runs, prints, builds = [], [], []
        # A run stopped by its cap and finished by a continuation is still one run: its continuation's
        # sessions join the run it names, so the pairs and repeats are counted once.
        by_id, order = {}, []
        for e in verdict_events:
            target = e.get("continues")
            if target and target in by_id:
                by_id[target].append(e)
            else:
                by_id[e["id"]] = [e]
                order.append(e["id"])
        for run_id in order:
            lines = []
            for e in by_id[run_id]:
                if not e["runs_file"]:
                    continue
                # os.path.join keeps an absolute runs_file as it is.
                path = os.path.join(root, e["runs_file"])
                if os.path.exists(path):
                    lines += _read_lines(path)
            runs.append(lines)
            prints.append(_fingerprints(lines))
            for line in lines:
                b = line.get("build")
                if b:
                    pair = (b.get("binary_version"), (b.get("commit") or "")[:7])
                    if pair not in builds:
                        builds.append(pair)
        verdict = evaluate_skill(runs, skill, heldout.get(skill))
        changed = sorted(
            task
            for task in {t for p in prints for t in p}
            if len({p[task] for p in prints if task in p}) > 1
        )
        if changed and not verdict["verdict"].startswith("no verdict"):
            verdict = {
                **verdict,
                "verdict": f"no verdict (task file changed between runs: {', '.join(changed)})",
            }
        row = {
            **{k: v for k, v in verdict.items() if k != "runs"},
            "run_results": verdict.get("runs", []),
            "ledger_ids": [e["id"] for e in mine],
            "spend_usd": round(sum(e.get("cost_usd") or 0.0 for e in mine), 4),
            "builds": builds,
            "models": sorted(
                {f"{m} {e or 'default effort'}" for lines in runs for m, e in _models(lines) if m}
            ),
            "train_runs": sum(1 for e in mine if e.get("purpose") == "train"),
            "heldout_tasks": sorted(heldout.get(skill, ())),
        }
        if report["refused"]:
            row["verdict"] = "refused: criteria.md changed"
        report["skills"][skill] = row
    return report


# --- rendering -------------------------------------------------------------------------------------------


def _ci(ci, fmt="{:+.2f}"):
    if not ci or ci[0] is None:
        return "n/a"
    return f"[{fmt.format(ci[0])}, {fmt.format(ci[1])}]"


def _models_text(row: dict) -> str:
    return ", ".join(row.get("models", [])) or "not recorded (sessions before 135 carry none)"


def render_row(skill: str, row: dict) -> str:
    if not row.get("run_results") and "pairs" not in row:
        held = row.get("heldout_tasks", [])
        return (
            f"{skill}\n  verdict   {row['verdict']}\n"
            f"  model     {_models_text(row)}\n"
            f"  ledger    {', '.join(row.get('ledger_ids', [])) or 'none'}   spend "
            f"${row.get('spend_usd', 0):.2f}   train runs {row.get('train_runs', 0)}\n"
            f"  held out  {len(held)} task(s): {', '.join(held) or '-'}"
        )
    runs = row.get("run_results") or [row]
    first = runs[0]
    builds = (
        ", ".join(f"{v} {c}" for v, c in row.get("builds", [])) or "no build recorded"
    )
    lines = [
        f"{skill}",
        f"  verdict   {row['verdict']}"
        + (f"  ({', '.join(row['kinds'])})" if row.get("kinds") else ""),
        f"  model     {_models_text(row)}",
        f"  ledger    {', '.join(row.get('ledger_ids', [])) or 'none'}   spend ${row.get('spend_usd', 0):.2f}   "
        f"train runs {row.get('train_runs', 0)}   build {builds}",
        f"  pairs     {first['pairs']}  b={first['b']} c={first['c']}  loaded "
        + ("n/a" if first["loaded_rate"] is None else f"{first['loaded_rate']:.0%}")
        + f"  unloaded {first['unloaded']}  unscored {first['unscored']}  tasks {len(first['tasks'])}",
    ]
    if first.get("calls_ratio") is not None:
        lines.append(
            f"  calls     ratio {first['calls_ratio']:.2f} 95% {_ci(first.get('calls_ratio_ci'), '{:.2f}')}"
            f"  diff/pair {first['calls_diff']:+.1f} 95% {_ci(first.get('calls_diff_ci'), '{:+.1f}')}"
        )
    if first.get("cost_ratio") is not None:
        lines.append(
            f"  cost      ratio {first['cost_ratio']:.2f} 95% {_ci(first.get('cost_ratio_ci'), '{:.2f}')}"
            f"  diff/pair {first['cost_diff']:+.2f} 95% {_ci(first.get('cost_diff_ci'))}"
            f"  cheaper in {first['share_cheaper']:.0%} of tasks"
        )
    tok = first.get("tokens") or {}
    if tok:
        def one(t):
            return (
                f"in {t.get('input', 0):,} out {t.get('output', 0):,} "
                f"cache r{t.get('cache_read', 0):,}/w{t.get('cache_write', 0):,}"
            )
        lines.append(f"  tokens    tools {one(tok.get('tools', {}))} | treated {one(tok.get('treated', {}))}")
    if first.get("quality_available"):
        lines.append(
            f"  quality   diff {first['quality_diff']:+.2f} 95% {_ci(first.get('quality_diff_ci'))}"
        )
    if first["thin_tasks"] or first["excluded_tasks"]:
        lines.append(
            f"  left out  thin {first['thin_tasks'] or '-'}  not held out {first['excluded_tasks'] or '-'}"
        )
    return "\n".join(lines)


def render_markdown(report: dict) -> str:
    """The same figures as `render`, as tables for results.md."""
    if report["refused"]:
        return f"REFUSED: {report['refused']}"
    out = []
    for skill, row in report["skills"].items():
        runs = row.get("run_results") or []
        out.append(f"### {skill}\n")
        out.append(f"Verdict: **{row['verdict']}**" + (f" ({', '.join(row['kinds'])})" if row.get("kinds") else ""))
        builds = ", ".join(f"{v} at {c}" for v, c in row.get("builds", [])) or "no build recorded"
        out.append(
            f"\nLedger: {', '.join(row.get('ledger_ids', [])) or 'none'}. Spend ${row.get('spend_usd', 0):.2f}. "
            f"Model: {_models_text(row)}. Build: {builds}. Held-out tasks: {', '.join(row.get('heldout_tasks', [])) or 'none'}. "
            f"Train runs: {row.get('train_runs', 0)}.\n"
        )
        for number, one in enumerate(runs, start=1):
            if "pairs" not in one:
                continue
            out.append(f"Run {number}: {one['verdict']}\n")
            out.append("| Measure | Value | 95% interval |\n| --- | --- | --- |")
            out.append(f"| Usable pairs | {one['pairs']} | |")
            out.append(f"| Only the skill passed (b) | {one['b']} | |")
            out.append(f"| Only tools passed (c) | {one['c']} | |")
            rate = one["loaded_rate"]
            out.append(f"| Skill loaded in treated sessions | {'n/a' if rate is None else f'{rate:.0%}'} | |")
            out.append(f"| Unloaded / unscored pairs | {one['unloaded']} / {one['unscored']} | |")
            if one.get("calls_ratio") is not None:
                out.append(f"| Calls ratio (treated / tools) | {one['calls_ratio']:.2f} | {_ci(one.get('calls_ratio_ci'), '{:.2f}')} |")
                out.append(f"| Calls difference per pair | {one['calls_diff']:+.1f} | {_ci(one.get('calls_diff_ci'), '{:+.1f}')} |")
            if one.get("cost_ratio") is not None:
                out.append(f"| Cost ratio (treated / tools) | {one['cost_ratio']:.2f} | {_ci(one.get('cost_ratio_ci'), '{:.2f}')} |")
                out.append(f"| Cost difference per pair (USD) | {one['cost_diff']:+.2f} | {_ci(one.get('cost_diff_ci'))} |")
                out.append(f"| Tasks where the treated arm cost less | {one['share_cheaper']:.0%} | |")
            if one.get("quality_available"):
                out.append(f"| Quality difference | {one['quality_diff']:+.2f} | {_ci(one.get('quality_diff_ci'))} |")
            tok = one.get("tokens") or {}
            for arm in ("tools", "treated"):
                t = tok.get(arm) or {}
                if t:
                    out.append(
                        f"| Tokens, {arm} | in {t.get('input', 0):,}, out {t.get('output', 0):,}, "
                        f"cache read {t.get('cache_read', 0):,} / write {t.get('cache_write', 0):,} | |"
                    )
            crit = one.get("criteria", {})
            out.append(
                f"\nCriteria on this run: 1 {crit.get('1')}, 2a {crit.get('2a')}, 2b {crit.get('2b')}, "
                f"2c {crit.get('2c')}. Left out: thin {one.get('thin_tasks') or '-'}, not held out "
                f"{one.get('excluded_tasks') or '-'}.\n"
            )
        if row.get("replication"):
            r = row["replication"]
            out.append(
                f"Replication: pooled route {r['pooled']}, direction route {r['direction']}, "
                f"kinds replicated {', '.join(r['kinds']) or 'none'}.\n"
            )
    return "\n".join(out)


def render(report: dict) -> str:
    if report["refused"]:
        return f"REFUSED: {report['refused']}"
    return "\n\n".join(
        render_row(skill, row) for skill, row in report["skills"].items()
    )


# --- the command ------------------------------------------------------------------------------------------

READ_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "tasks", "skills", "read.toml")
)


def load_read(path: str = READ_PATH) -> dict:
    """Tasks whose transcripts or outcomes someone read to decide an edit, each with the reason.

    A read task is train, whatever the split file says: it cannot give a held-out figure.
    """
    import tomllib

    if not os.path.exists(path):
        return {}
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    out = {}
    for task, entry in raw.items():
        reason = entry.get("reason") if isinstance(entry, dict) else None
        if not str(reason or "").strip():
            raise ValueError(f"{path}: {task} needs a reason; a bare entry cannot be audited")
        out[task] = str(reason)
    return out


def heldout_by_skill(tasks, split, read) -> dict:
    """Per skill, the tasks on the holdout side that nobody read."""
    held = defaultdict(set)
    for task in tasks:
        if task.skill and task.id in split.holdout and task.id not in read:
            held[task.skill].add(task.id)
    return dict(held)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Per-skill verdicts against criteria.md. Free.")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--criteria", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--markdown", action="store_true", help="tables for results.md")
    args = parser.parse_args(argv)

    from tests.e2e.skill_eval import graded_task
    from tests.e2e.skill_eval.split import default_split

    events = []
    if os.path.exists(args.ledger):
        with open(args.ledger, encoding="utf-8") as handle:
            for line in handle:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
    tasks = graded_task.skill_corpus()
    held = heldout_by_skill(tasks, default_split(), set(load_read()))
    report = skills_report(
        events,
        criteria_path=args.criteria,
        heldout=held,
        task_skill={t.id: t.skill for t in tasks},
        root=args.root,
    )
    print(render_markdown(report) if args.markdown else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
