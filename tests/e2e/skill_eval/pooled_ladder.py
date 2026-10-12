"""Pool the tools-ladder shards into one `tools` vs `tools+skills` comparison.

    python3 -m tests.e2e.skill_eval.pooled_ladder tests/e2e/results/ladder-A.runs.jsonl ...

The run is split across containers, so its sessions are in several files. This pairs each task's two arms
across them. It refuses files from different models or efforts. It reports how often a `tools+skills`
session called the `skill` tool: with every skill installed and none preloaded that rate says whether a
lift comes from skill content or only from the skill index being in the context.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict

from tests.e2e.skill_eval.evidence import _cost_per_pass, bootstrap_interval, mcnemar_exact

BASE, TREATED = "tools", "tools+skills"


class PoolRefused(RuntimeError):
    """The files cannot be pooled without mixing what was measured."""


def _lines(paths):
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for raw in handle:
                if raw.strip():
                    yield json.loads(raw)


def _mean(xs):
    return sum(xs) / len(xs)


def pool(paths) -> dict:
    lines = list(_lines(paths))
    models = {(x.get("model"), x.get("effort")) for x in lines}
    if len(models) > 1:
        raise PoolRefused(f"the files name more than one model or effort: {sorted(map(str, models))}")
    sessions = {}
    for x in lines:
        if x["arm"] not in (BASE, TREATED):
            continue
        key = (x["task_id"], x["arm"], x["run_index"])
        # A later line replaces an earlier one, except that an unscored one never replaces a scored one.
        if key in sessions and x["passed"] is None and sessions[key]["passed"] is not None:
            continue
        sessions[key] = x
    pairs, unscored = [], 0
    for task, arm, repeat in sorted(k for k in sessions if k[1] == BASE):
        t, s = sessions[(task, arm, repeat)], sessions.get((task, TREATED, repeat))
        if s is None:
            continue
        if t["passed"] is None or s["passed"] is None:
            unscored += 1
        else:
            pairs.append((task, t, s))
    treated = [x for x in sessions.values() if x["arm"] == TREATED]
    loaded = sum(1 for x in treated if any(c.get("name") == "skill" for c in x.get("calls") or ()))
    by_task = defaultdict(list)
    for task, t, s in pairs:
        by_task[task].append((t, s))
    lifts = [_mean([s["passed"] - t["passed"] for t, s in group]) for group in by_task.values()]
    tools_calls = sum(t["tool_calls"] for _, t, _ in pairs)
    tools_cost = sum(t.get("cost_usd") or 0 for _, t, _ in pairs)
    model, effort = next(iter(models)) if models else (None, None)
    return {
        "model": model,
        "effort": effort,
        "pairs": len(pairs),
        "tasks": len(by_task),
        "unscored": unscored,
        "b": sum(1 for _, t, s in pairs if s["passed"] and not t["passed"]),
        "c": sum(1 for _, t, s in pairs if t["passed"] and not s["passed"]),
        "mcnemar_p": mcnemar_exact(
            sum(1 for _, t, s in pairs if s["passed"] and not t["passed"]),
            sum(1 for _, t, s in pairs if t["passed"] and not s["passed"]),
        ),
        "tools_cost_per_pass": _cost_per_pass([t for _, t, _ in pairs]),
        "treated_cost_per_pass": _cost_per_pass([s for _, _, s in pairs]),
        "tools_passes": sum(1 for _, t, _ in pairs if t["passed"]),
        "treated_passes": sum(1 for _, _, s in pairs if s["passed"]),
        "lift": _mean(lifts) if lifts else None,
        "lift_ci": bootstrap_interval(lifts, _mean) if lifts else (None, None),
        "calls_ratio": sum(s["tool_calls"] for _, _, s in pairs) / tools_calls if tools_calls else None,
        "cost_ratio": sum(s.get("cost_usd") or 0 for _, _, s in pairs) / tools_cost if tools_cost else None,
        "treated_sessions": len(treated),
        "skill_sessions": loaded,
        "skill_load_rate": loaded / len(treated) if treated else None,
    }


def _usd(value) -> str:
    return "n/a" if value is None else f"${value:.3f}"


def render(r: dict) -> str:
    low, high = r["lift_ci"]
    ci = "n/a" if low is None else f"[{low:+.3f}, {high:+.3f}]"
    rate = "n/a" if r["skill_load_rate"] is None else f"{r['skill_load_rate']:.0%}"
    return "\n".join(
        [
            f"tools vs tools+skills on {r['model']} {r['effort'] or 'default effort'}",
            f"  pairs {r['pairs']} over {r['tasks']} tasks, unscored {r['unscored']}",
            f"  only skills passed (b) {r['b']}, only tools passed (c) {r['c']}; "
            f"passes {r['tools_passes']} tools / {r['treated_passes']} with skills",
            f"  lift {r['lift']:+.3f} 95% {ci} (mean over tasks of the per-task pass-rate difference)"
            if r["lift"] is not None
            else "  lift n/a",
            f"  calls ratio {r['calls_ratio']:.2f}, cost ratio {r['cost_ratio']:.2f}"
            if r["calls_ratio"] and r["cost_ratio"]
            else "  ratios n/a",
            f"  McNemar p {r['mcnemar_p']:.3f}; cost per pass: tools "
            + _usd(r["tools_cost_per_pass"])
            + ", with skills "
            + _usd(r["treated_cost_per_pass"]),
            f"  {r['skill_sessions']} of {r['treated_sessions']} tools+skills sessions ({rate}) loaded a skill",
        ]
    )


def main(argv=None) -> int:
    paths = list(sys.argv[1:] if argv is None else argv)
    if not paths:
        print(__doc__)
        return 2
    print(render(pool(paths)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
