# .improve

The improvement loop as a layer you apply to a project. Run `.improve/improve status` to see where the
loop stands and `.improve/improve next` to work the top item. Both are free: they never start a model
session.

```text
$ .improve/improve status
Nightly canary       green (2026-10-10)
Last full holdout    2026-09-19, 41 tasks
                     tools alone 34/41  ·  with skills 38/41
Worklist             1. CORPUS-40  fails in both arms   <- next
...
```

## What is in here

| Path                      | What it is                                                                                |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| `project.toml`            | The adapter. Every fact about this project. The only file a new project edits.            |
| `engine/improve.py`       | The engine. Knows the loop, nothing about the project. Standard library + YAML.           |
| `improve`                 | A shell wrapper: runs the engine from the project root.                                   |
| `tests/`                  | Tests that run the engine on a made-up project, and guard that it stays generic.          |
| `CONTEXT.md`              | The glossary: task, arm, holdout, worklist, ledger and the rest.                          |
| `adr/` (repo `docs/adr/`) | Why the loop is shaped this way: 0002 (engine and adapter), 0003 (evidence).              |
| `ledger.jsonl`            | Append-only record of what the loop did and spent. Created by the first verb that spends. |
| `validated.json`          | A local cache of which tasks were checked sound. Not committed.                           |

## Using it in another project

1. Copy `.improve/` into the project.
2. Rewrite `project.toml`. The comments in this repo's copy say what each key means. Unknown keys are an
   error, so a typo cannot quietly fall back to a default.
3. Make the project's run records match the contract below, or write a small converter that does.
4. Run `.improve/improve status`.

The engine needs Python 3.11 and PyYAML. Nothing else.

## The run record the engine reads

A JSON file in `results_dir` whose name matches `record_glob`:

```json
{
  "runs": [
    {
      "task_id": "T-1",
      "arm": "plain",
      "passed": true,
      "tool_calls": 7,
      "seconds": 41.2,
      "timed_out": false,
      "side": "holdout"
    }
  ],
  "provenance": { "measured_at": "2026-09-19T06:48:40Z" },
  "published": ["plain -> memory  lift +0.098 [-0.034, +0.229]  n=41 pairs ..."]
}
```

- `runs`: one entry per session. A task with several repeats has several entries per arm; the engine
  counts a task as passed in an arm when most of its repeats passed.
- `side` is optional. A run whose side is in `excluded_sides` (for example `train`) disqualifies the
  whole record, so a figure fitted to training tasks is never reported as the result.
- `measured_at` orders records; without it the file's modification time is used.
- `published` is optional. The line containing `published_marker` is shown as the result.

A record is a **full holdout** when it covers at least `min_tasks` tasks and has both the baseline and
the treated arm.

## Verbs

- `status [--json]`: the nightly, the last full holdout, a ranked worklist, this month's spend.
  `--json` is for a morning brief or any other tool that wants the same facts. Free.
- `next [task]`: take the top worklist item (or the one named), check the task is sound by running the
  adapter's `[[validate]]` command, and show what failed. A broken task is reported as the problem
  before the agent is blamed. The check is cached by the task file's hash. Free.
- `try [task] [--yes] [--cap N] [--repeats N]`: after you change something, re-run one task and say
  whether the change helped. **This one spends money.** It checks the task is sound first, shows the
  harness's own estimate (with the adapter's warning about it), shows the weekly budget left, and asks.
  The run gets a cap that is the smaller of `--cap` (default `per_try_usd`) and what is left of
  `per_week_usd`; the cap is the bound, not the estimate. Without a terminal and without `--yes` it
  does not run.

### What `try` writes

Every run is an iteration with an id, `IMP-NNNN`, and leaves three lines in `ledger.jsonl`:

```json
{"ts":"2026-10-12T09:00:00Z","id":"IMP-0003","event":"claim","who":"tom","task":"CORPUS-40"}
{"ts":"2026-10-12T09:11:40Z","id":"IMP-0003","event":"run","who":"tom","task":"CORPUS-40","cost_usd":2.41,"sessions":6,"returncode":0,"aborted":false,"cap":5.0,"repeats":3,"record":"tests/e2e/results/try-IMP-0003.json"}
{"ts":"2026-10-12T09:11:41Z","id":"IMP-0003","event":"verdict","task":"CORPUS-40","label":"better","before":{"tools":[0,1],"tools+skills":[0,1]},"after":{"tools":[1,3],"tools+skills":[3,3]},"record":"tests/e2e/results/try-IMP-0003.json"}
```

- **One holder per item.** A `claim` with no `verdict` yet is held by whoever wrote it. Someone else's
  `try` on that task is refused; the holder can run it again and keeps the same id.
- **Labels** are `fixed` (every arm that was failing now passes every repeat, nothing got worse),
  `better`, `no change`, `worse`, `mixed`, or `incomplete` (the run was cut off; its spend is still
  recorded). Three repeats show a direction, not proof, and the output says so.
- **No identifier, no claim.** To say a change improved something, commit it with the trailer
  `Improve: IMP-NNNN`. The verdict line is what the claim points at (ADR 0003).
- Commit `ledger.jsonl`. It is the project's record of what the loop did and spent.

The weekly holdout run is not built yet.
