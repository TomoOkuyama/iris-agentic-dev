# Plan: skill evidence

## Order

1. Criteria and this spec, committed first.
2. Infrastructure, one test-first commit each: `improve skills`, tokens, authoring kit,
   `quality_checks`, `improve try` rules for new tasks and containers, binary guard, then the weekly
   budget raise.
3. Checkpoint to Tom after infrastructure items 1 to 4.
4. Per skill, in the candidate order of the goal: usable-task audit, authoring, train measurement,
   at most a few generic edits, one held-out measurement, one replication.
5. `results.md` and the article draft.

## Decisions

- The engine stays project-blind. `improve skills` calls the command the adapter names in
  `[skills]`; the verdict code is `tests/e2e/skill_eval/evidence.py`.
- New tasks live in `tests/e2e/tasks/skills/<skill>/`. The loader walks the subdirectories, and
  `split.toml` still has to give every id exactly one side.
- The held-out run for skill S is `ladder --ladder skill --skill S --side holdout`, arms `tools` and
  `tools+S`, three repeats, one run id. A replication is a second invocation with its own run id.
- Direct ladder invocations write ledger events through `improve measure`, so spend and the
  criteria hash are recorded the same way `improve try` records them.
- Session cost is the measured `part.cost`; the weekly guard in `project.toml` is raised to the
  total budget in its own commit.

## Risks

- A single container is shared by all runs, so runs are serial. A full measurement of one skill
  (5 tasks, 3 repeats, 2 arms) is 30 sessions.
- Authoring knowledge-gap tasks takes live probes; each fact is verified on `iris-dev-iris` first.
- Few skills may qualify. That is a result.
