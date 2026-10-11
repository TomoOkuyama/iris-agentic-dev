# 135 criteria: what "net positive" means for a skill

Written 2026-10-10, before any measurement run in 135. This file is the pre-registration. Each ledger
`run` event for a 135 measurement carries its sha256, and `improve skills` refuses a verdict if the
file on disk no longer hashes to the value in the first 135 run event. A change to a criterion after
that is a new study with new runs, not an edit.

## Units

- **Session**: one opencode run of one task in one arm, with a recorded verdict from the task's check.
- **Pair**: the same task and repeat index in arm `tools` and arm `tools+S`, from the same run id.
- **Scored session**: the check answered PASS or FAIL. A timeout whose check answered is scored. A
  session whose check never answered is **unscored**; its pair is dropped and the drop is reported.
- **Loaded**: the treated session called the `skill` tool on S (`skill_loaded` true).
- **Usable pair**: both sessions scored and the treated session loaded S. Unloaded treated sessions
  are excluded from every figure below and are reported with their count and their pass figures.
- **b**: usable pairs where only the treated session passed. **c**: usable pairs where only the
  `tools` session passed.
- **Task cost / task calls**: the mean over a task's usable pairs. Cost is measured `part.cost`
  summed over `step_finish` events; calls are completed tool calls.

## Eligibility for a verdict

A skill S gets a verdict only when all hold, otherwise its row says `no verdict` and why:

1. At least 5 held-out tasks for S, each with at least 2 usable pairs. A held-out task is one that
   nobody read a transcript of, or edited a skill or tool against, and whose side in `split.toml` was
   fixed before any session of it ran. A task that fails this moves to train and is recorded.
2. 3 repeats per task and arm.
3. Arms `tools` and `tools+S` (S preloaded) in the same run id, so the baseline is measured alongside
   the treatment against the same binary.
4. S loaded in at least 90 percent of scored treated sessions.
5. Every session of the run names one binary version and one commit, and the checkout was clean when
   the run started.

## Net positive

S is net positive when criteria 1, 2 and 3 all hold on its held-out tasks.

1. **Not worse on completion.** b is at least c.
2. **At least one of**
   - **a. Completion.** b minus c is at least 3, and c is at most 1.
   - **b. Efficiency.** Mean calls of the treated arm over mean calls of `tools` is at most 0.75, and
     the same ratio for cost is at most 0.80, with at least 75 percent of the tasks cheaper (task cost
     of the treated arm below the task cost of `tools`), and the 95 percent task-clustered bootstrap
     interval for the per-task mean difference (treated minus tools) excludes zero for both cost and
     calls (both upper bounds below zero). The ratios are ratios of means over all usable pairs.
   - **c. Quality.** The per-session quality score is the fraction of the task's `quality_checks` that
     print PASS, declared in the task file before the first session. The mean per-task difference
     (treated minus tools) is at least 0.15, its 95 percent task-clustered bootstrap interval has a
     lower bound above zero, and the treated arm's pass count is at least the `tools` arm's.
3. **Replicated.** A second run (new run id, fresh sessions, a new binary build if code changed
   between runs) meets criterion 1 by itself, and either
   - the pooled data of both runs meet criterion 1 and the same part of criterion 2 (same numbers,
     on the pooled pairs and the pooled tasks), or
   - on every task that decided the first run, the second run agrees in direction. For completion a
     task decided the run when it had b or c above zero; it agrees when the sign of its (b minus c)
     is the same in the second run and not zero. For efficiency every task decides, and a task agrees
     when its task cost and its task calls are both below the `tools` arm's again.

Anything else is **not net positive**, reported with its numbers. The kind of win is the part of
criterion 2 that held: `completion`, `efficiency` or `quality`. A skill can hold more than one.

## Intervals

- 95 percent percentile bootstrap, 10000 resamples, seed 135, resampling **tasks** with replacement
  and taking each resampled task's usable-pair means, so repeats of a task are never treated as
  independent.
- Every figure in a report carries its interval or its exact counts. A ratio of means is reported
  with the bootstrap interval of the ratio.

## What does not count

- Any arm other than a single preloaded skill on top of `tools` (the pooled `tools+skills` arm had
  0 loaded sessions in 58 and measures only the skill index).
- A baseline from an earlier run. A task measured twice in different runs enters the pooled data
  only for criterion 3 and only if both runs name the same task file hash.
- A task read or edited against. Its figures are train figures and are not in any verdict.
- A repeat dropped because it was unfavourable. Unscored sessions are dropped only under the rule
  above and are listed.

## Budget

135 spends at most 300 USD, 5 USD per try, 60 USD per skill, from measured `step_finish` cost. A stop
and a summary at every 50 USD, and at once when a run reaches its cap.
