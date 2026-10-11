# Results: skill evidence

Written as the runs land. Every figure is read from `tests/e2e/results/ladder-*.runs.jsonl` and
`.improve/ledger.jsonl` by `improve skills` (`python3 -m tests.e2e.skill_eval.evidence --markdown`
gives the tables below). Nothing here is typed in from memory.

## How to read this

- The bar is `criteria.md`, committed before the first run. Its sha256 is on every ledger event
  (`4b2daef8…`). It changed once before any run: I added the rule that a later run must itself point
  the same way for pooled replication to count, and the paragraph on intervals and eligibility.
- A skill is **net positive** only when its first held-out run meets criteria 1 and 2 and a second
  run replicates it (criterion 3). Nothing has been replicated yet unless a table says so.
- Held-out tasks are tasks nobody read a transcript of or edited against. Seven older skill tasks
  were read while editing skills in 130 and 132 and moved to train (`tests/e2e/tasks/skills/read.toml`).
  The tasks I authored in 135 were written from the skill text, so they test whether the skill's own
  facts help. They do not test whether the skill helps on work I did not think of.
- Every session ran with gpt-4.1 through opencode, with the iad tools. The `tools` arm has the tools.
  The `tools+<skill>` arm adds one skill, preloaded, with the instruction to load it.
- Cost is opencode's measured `step_finish.cost`. Tokens come from the same events.

## Outcome

**No skill is net positive on the pre-registered bar.** One, `objectscript-guardrails`, met the
completion criterion on its first held-out run and has not been replicated, because a replication
costs about $50 and its per-skill cap has $5.41 left. Five more ran a complete held-out run and did not
meet the bar. One, `iris-sql`, was stopped by its per-run cap and has no verdict. Three candidates were
not run: `objectscript-unit-test`, `ensemble-production` and `iris-ai-hub`.

| Skill                        | Run              | Held-out tasks | Pairs | Only skill (b) | Only tools (c) | Passes tools / skill | Calls ratio | Cost ratio | Verdict                                          |
| ---------------------------- | ---------------- | -------------- | ----- | -------------- | -------------- | -------------------- | ----------- | ---------- | ------------------------------------------------ |
| `objectscript-guardrails`    | IMP-0011 to 0013 | 7              | 21    | 10             | 0              | 9 / 19               | 1.29        | 1.66       | first run qualifies (completion), not replicated |
| `iris-query-plans`           | IMP-0014         | 5              | 15    | 4              | 2              | 10 / 12              | 1.16        | 0.96       | not net positive                                 |
| `objectscript-sql-patterns`  | IMP-0015         | 5 of 6         | 15    | 5              | 2              | 10 / 13              | 1.02        | 1.45       | not net positive                                 |
| `iris-agentic-dev`           | IMP-0016         | 5              | 15    | 1              | 2              | 13 / 12              | 0.71        | 0.83       | not net positive                                 |
| `objectscript-tdd`           | IMP-0017         | 5              | 15    | 0              | 0              | 15 / 15              | 1.06        | 1.23       | not net positive                                 |
| `objectscript-list-patterns` | IMP-0018         | 5 of 6         | 14    | 5              | 2              | 3 / 6                | 1.29        | 1.37       | not net positive                                 |
| `iris-sql`                   | IMP-0019         | 5              | 6     | 0              | 3              | 6 / 3                | 1.87        | 1.76       | no verdict: stopped at the cap, 2 repeats        |

Intervals are in the per-skill tables below. All seven runs had the skill loaded in 100% of treated
sessions.

Why each one failed, in the terms of the criteria:

- **`objectscript-guardrails`**: b minus c is 10, so completion holds (criterion 2a). The skill arm
  also cost more: cost ratio 1.66 with an interval of 1.21 to 2.81, and the skill arm was cheaper in
  14% of tasks. So the win is completion only, and it is unreplicated.
- **`iris-query-plans`**: b minus c is 2, under the 3 needed. Cost and calls show no reliable change.
- **`objectscript-sql-patterns`** and **`objectscript-list-patterns`**: b minus c is 3, but c is 2 and
  completion allows at most 1. Both cost more than tools alone.
- **`iris-agentic-dev`**: b is below c, so criterion 1 fails. Calls ratio 0.71 (0.48 to 0.97) and
  cost ratio 0.83 (0.64 to 1.06) look like an efficiency win, but efficiency only counts when
  completion is not worse.
- **`objectscript-tdd`**: both arms passed all 15 pairs. The skill added cost.
- **`iris-sql`**: see Stopped.

## Budget

Total measured spend $237.69 of $300. Ledger events IMP-0011 to IMP-0019 hold every figure. Per
skill: guardrails $54.59, query-plans $48.32, sql-patterns $42.27, agentic-dev $4.82, tdd $11.50,
list-patterns $35.09, iris-sql $41.10. A session costs from $0.09 to $6.51 and a 30-session run
$5 to $48. The per-run cap ($40) stopped two runs; the continuation of guardrails (IMP-0012, IMP-0013)
finished its missing 5 sessions from a worktree at the same commit with the same binary sha256
(`3f28647770eb…`), so it is one run on one build.

Stops at each $50 were reported as they happened (at $54.59, $102.91, $150.00, $196.59 and $237.69).

## What was not done, and why

- **No replication of any skill.** The only candidate is `objectscript-guardrails`. Its second run
  would cost about $50 (the five tasks that decided the first run cost $51), against $5.41 left in
  its per-skill cap. Under `criteria.md` it is therefore not net positive.
- **`iris-sql` stopped** at 17 of 30 sessions with $18.90 left under its cap and about $30 of sessions
  owing. On the 6 usable pairs only tools passed in 3 and the skill arm used 1.9 times the calls. It
  is not a verdict.
- **`objectscript-unit-test`, `ensemble-production`, `iris-ai-hub`** were not run. They need new
  held-out tasks (their older tasks were read while editing the skills), and the budget did not
  reach them.
- **No improvement cycle.** I made no edit to any skill in 135. No held-out run came close enough to
  the bar to justify spending on train tasks, and `objectscript-guardrails` was settled before 135.
- **Quality criterion (2c)** was never available: no held-out task declares `quality_checks`.
- Two tasks have unused reserves: `objectscript-sql-patterns` SKILL-32 and
  `objectscript-list-patterns` SKILL-47. The five measured per skill were fixed by task id before any
  session ran.

## Deviations I made, and the reason

- `criteria.md` was edited once, before any run, to make pooled replication stricter and to state how
  tasks with fewer than 2 pairs and the quality criterion are handled. Its hash has not changed since.
- Seven older skill tasks (SKILL-02, 03, 05, 09, 16, 24, 25) moved from holdout to train because their
  transcripts were read to decide edits in 130 and 132. `iris-ai-hub` lost both of its held-out tasks
  that way.
- The tasks I authored (SKILL-26 to SKILL-51) came from the facts in each skill's text, each checked
  live on IRIS 2026.2 as false against the stub and true against the reference. They measure whether a
  skill helps where its own facts apply. They are not a sample of everyday work.
- Held-out outcomes were looked at only through `improve skills`. I read no held-out transcript.
- The ladder's per-session timeout of 300 s counts: one `iris-sql` skill-arm session timed out at
  $6.51 and is a scored failure.

## Stopped

`iris-sql` (IMP-0019) has 2 of 3 repeats and 6 usable pairs. The table below is the partial figure
the report gives, with the verdict "no verdict (fewer than 3 repeats)".

## Tables

### iris-agentic-dev

Verdict: **not net positive**

Ledger: IMP-0016. Spend $4.82. Build: 1.5.0 at d39e7cc. Held-out tasks: SKILL-18, SKILL-41, SKILL-42, SKILL-43, SKILL-44. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 15                                                     |                |
| Only the skill passed (b)             | 1                                                      |                |
| Only tools passed (c)                 | 2                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 0                                                  |                |
| Calls ratio (treated / tools)         | 0.71                                                   | [0.48, 0.97]   |
| Calls difference per pair             | -1.7                                                   | [-2.9, -0.2]   |
| Cost ratio (treated / tools)          | 0.83                                                   | [0.64, 1.06]   |
| Cost difference per pair (USD)        | -0.03                                                  | [-0.07, +0.01] |
| Tasks where the treated arm cost less | 80%                                                    |                |
| Tokens, tools                         | in 668,420, out 12,348, cache read 2,415,104 / write 0 |                |
| Tokens, treated                       | in 585,042, out 8,498, cache read 1,920,512 / write 0  |                |

Criteria on this run: 1 False, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### iris-query-plans

Verdict: **not net positive**

Ledger: IMP-0014. Spend $48.32. Build: 1.5.0 at 8e92d72. Held-out tasks: SKILL-20, SKILL-33, SKILL-34, SKILL-35, SKILL-36. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 15                                                        |                |
| Only the skill passed (b)             | 4                                                         |                |
| Only tools passed (c)                 | 2                                                         |                |
| Skill loaded in treated sessions      | 100%                                                      |                |
| Unloaded / unscored pairs             | 0 / 0                                                     |                |
| Calls ratio (treated / tools)         | 1.16                                                      | [0.85, 1.62]   |
| Calls difference per pair             | +5.5                                                      | [-6.6, +16.1]  |
| Cost ratio (treated / tools)          | 0.96                                                      | [0.68, 1.42]   |
| Cost difference per pair (USD)        | -0.07                                                     | [-0.66, +0.51] |
| Tasks where the treated arm cost less | 40%                                                       |                |
| Tokens, tools                         | in 3,243,776, out 50,656, cache read 35,628,672 / write 0 |                |
| Tokens, treated                       | in 4,095,271, out 56,832, cache read 29,943,680 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### iris-sql

Verdict: **no verdict (fewer than 3 repeats (2))**

Ledger: IMP-0019. Spend $41.10. Build: 1.5.0 at 11d0808. Held-out tasks: SKILL-11, SKILL-48, SKILL-49, SKILL-50, SKILL-51. Train runs: 0.

Run 1: no verdict (fewer than 3 repeats (2))

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 6                                                         |                |
| Only the skill passed (b)             | 0                                                         |                |
| Only tools passed (c)                 | 3                                                         |                |
| Skill loaded in treated sessions      | 100%                                                      |                |
| Unloaded / unscored pairs             | 0 / 0                                                     |                |
| Calls ratio (treated / tools)         | 1.87                                                      | [1.33, 3.00]   |
| Calls difference per pair             | +20.7                                                     | [+4.0, +44.0]  |
| Cost ratio (treated / tools)          | 1.76                                                      | [1.37, 2.93]   |
| Cost difference per pair (USD)        | +1.04                                                     | [+0.29, +1.70] |
| Tasks where the treated arm cost less | 0%                                                        |                |
| Tokens, tools                         | in 1,185,382, out 17,328, cache read 11,328,640 / write 0 |                |
| Tokens, treated                       | in 2,562,414, out 23,231, cache read 18,182,272 / write 0 |                |

Criteria on this run: 1 False, 2a False, 2b False, 2c False. Left out: thin {'SKILL-50': 1, 'SKILL-51': 1}, not held out -.

### objectscript-guardrails

Verdict: **first run qualifies, awaiting replication** (completion)

Ledger: IMP-0011, IMP-0012, IMP-0013. Spend $54.59. Build: 1.5.0 at bd53cd5. Held-out tasks: SKILL-01, SKILL-04, SKILL-17, SKILL-26, SKILL-27, SKILL-28, SKILL-29. Train runs: 0.

Run 1: first run qualifies, awaiting replication

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 21                                                        |                |
| Only the skill passed (b)             | 10                                                        |                |
| Only tools passed (c)                 | 0                                                         |                |
| Skill loaded in treated sessions      | 100%                                                      |                |
| Unloaded / unscored pairs             | 0 / 0                                                     |                |
| Calls ratio (treated / tools)         | 1.29                                                      | [0.97, 1.83]   |
| Calls difference per pair             | +8.6                                                      | [-0.8, +17.4]  |
| Cost ratio (treated / tools)          | 1.66                                                      | [1.21, 2.81]   |
| Cost difference per pair (USD)        | +0.64                                                     | [+0.18, +1.17] |
| Tasks where the treated arm cost less | 14%                                                       |                |
| Tokens, tools                         | in 2,641,892, out 60,640, cache read 29,579,008 / write 0 |                |
| Tokens, treated                       | in 3,743,351, out 71,048, cache read 51,963,392 / write 0 |                |

Criteria on this run: 1 True, 2a True, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-list-patterns

Verdict: **not net positive**

Ledger: IMP-0018. Spend $35.09. Build: 1.5.0 at 13b02f4. Held-out tasks: SKILL-06, SKILL-07, SKILL-10, SKILL-45, SKILL-46, SKILL-47. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 14                                                        |                |
| Only the skill passed (b)             | 5                                                         |                |
| Only tools passed (c)                 | 2                                                         |                |
| Skill loaded in treated sessions      | 100%                                                      |                |
| Unloaded / unscored pairs             | 0 / 1                                                     |                |
| Calls ratio (treated / tools)         | 1.29                                                      | [0.97, 1.88]   |
| Calls difference per pair             | +6.1                                                      | [-2.7, +14.8]  |
| Cost ratio (treated / tools)          | 1.37                                                      | [0.88, 1.75]   |
| Cost difference per pair (USD)        | +0.28                                                     | [-0.25, +0.66] |
| Tasks where the treated arm cost less | 20%                                                       |                |
| Tokens, tools                         | in 2,315,852, out 43,614, cache read 16,409,600 / write 0 |                |
| Tokens, treated                       | in 3,209,889, out 43,834, cache read 22,669,312 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-sql-patterns

Verdict: **not net positive**

Ledger: IMP-0015. Spend $42.27. Build: 1.5.0 at 03022af. Held-out tasks: SKILL-08, SKILL-12, SKILL-15, SKILL-30, SKILL-31, SKILL-32. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 15                                                        |                |
| Only the skill passed (b)             | 5                                                         |                |
| Only tools passed (c)                 | 2                                                         |                |
| Skill loaded in treated sessions      | 100%                                                      |                |
| Unloaded / unscored pairs             | 0 / 0                                                     |                |
| Calls ratio (treated / tools)         | 1.02                                                      | [0.77, 1.26]   |
| Calls difference per pair             | +0.6                                                      | [-7.1, +8.3]   |
| Cost ratio (treated / tools)          | 1.45                                                      | [0.86, 2.24]   |
| Cost difference per pair (USD)        | +0.52                                                     | [-0.16, +1.35] |
| Tasks where the treated arm cost less | 40%                                                       |                |
| Tokens, tools                         | in 2,428,056, out 44,017, cache read 24,065,920 / write 0 |                |
| Tokens, treated                       | in 4,519,579, out 44,608, cache read 31,237,376 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-tdd

Verdict: **not net positive**

Ledger: IMP-0017. Spend $11.50. Build: 1.5.0 at b59b9cc. Held-out tasks: SKILL-19, SKILL-37, SKILL-38, SKILL-39, SKILL-40. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                    | 95% interval   |
| ------------------------------------- | -------------------------------------------------------- | -------------- |
| Usable pairs                          | 15                                                       |                |
| Only the skill passed (b)             | 0                                                        |                |
| Only tools passed (c)                 | 0                                                        |                |
| Skill loaded in treated sessions      | 100%                                                     |                |
| Unloaded / unscored pairs             | 0 / 0                                                    |                |
| Calls ratio (treated / tools)         | 1.06                                                     | [0.83, 1.56]   |
| Calls difference per pair             | +0.8                                                     | [-2.3, +4.6]   |
| Cost ratio (treated / tools)          | 1.23                                                     | [0.94, 1.81]   |
| Cost difference per pair (USD)        | +0.08                                                    | [-0.02, +0.17] |
| Tasks where the treated arm cost less | 40%                                                      |                |
| Tokens, tools                         | in 966,952, out 23,317, cache read 6,046,720 / write 0   |                |
| Tokens, treated                       | in 1,682,039, out 18,200, cache read 5,681,536 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-unit-test

Verdict: **no verdict (no held-out run yet)**

Ledger: none. Spend $0.00. Build: no build recorded. Held-out tasks: SKILL-14. Train runs: 0.
