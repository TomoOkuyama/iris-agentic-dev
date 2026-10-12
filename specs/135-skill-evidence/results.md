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
- The first study ran every session on gpt-4.1 through opencode, with the iad tools. The second ran on
  `gpt-6-luna` at high reasoning effort on Bedrock (see Second study). The two are never pooled: the model
  and effort are on every session line and the report keeps them in separate rows. The `tools` arm has the tools.
  The `tools+<skill>` arm adds one skill, preloaded, with the instruction to load it.
- Cost is opencode's measured `step_finish.cost`. Tokens come from the same events.

## Outcome

**One skill is net positive on the pre-registered bar, and only in the third study.**
`objectscript-list-patterns` meets criteria 1, 2a and 3 on `gpt-oss-120b`: kind **completion**, replicated by
an independent second run. On the first study (gpt-4.1) and the second (gpt-6-luna) no skill is net positive.
The table below is the first study (gpt-4.1). The bar was five skills; one qualifies, on a weaker model. The
second and third studies are below.

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

## Second study: gpt-6-luna on Bedrock, high effort

I moved the evals to Bedrock after the first study, because the gpt-4.1 key path was the expensive one and
Bedrock holds the model family. The model is `bedrock-oai/global.openai.gpt-6-luna` through Bedrock's
OpenAI-compatible endpoint with the long-term key `bclaude` uses, at reasoning effort high. The Converse
route cannot carry effort through opencode's Bedrock SDK (it rejects the `redactedContent` stream block),
so this route was needed. Prices are OpenAI's list rates ($0.10 in, $0.50 out, $0.01 cache read per million
tokens); Bedrock's own rate for the model was not checked.

Nothing from the gpt-4.1 study carries over, so every skill was measured again with its own paired `tools`
arm, same tasks, same criteria. The skill was loaded in 100% of treated sessions in every run.

| Skill                        | Run                    | Pairs | Only skill (b) | Only tools (c) | Passes tools / skill | Unscored | Calls ratio       | Cost ratio        |
| ---------------------------- | ---------------------- | ----- | -------------- | -------------- | -------------------- | -------- | ----------------- | ----------------- |
| `objectscript-guardrails`    | IMP-0047               | 20    | 0              | 0              | 20 / 20              | 1        | 0.81 [0.57, 1.16] | 0.88 [0.62, 1.30] |
| `objectscript-guardrails`    | IMP-0050 (replication) | 21    | 0              | 2              | 21 / 19              | 0        | 0.79 [0.53, 1.14] | 0.94 [0.67, 1.25] |
| `iris-query-plans`           | IMP-0048               | 14    | 0              | 1              | 14 / 13              | 1        | 0.93 [0.64, 1.39] | 1.01 [0.78, 1.27] |
| `objectscript-sql-patterns`  | IMP-0053               | 17    | 0              | 1              | 17 / 16              | 1        | 0.89 [0.78, 0.98] | 1.09 [0.95, 1.32] |
| `iris-agentic-dev`           | IMP-0049               | 15    | 0              | 0              | 15 / 15              | 0        | 0.84 [0.68, 1.04] | 1.76 [1.63, 1.95] |
| `objectscript-tdd`           | IMP-0051               | 13    | 0              | 1              | 13 / 12              | 2        | 1.05 [0.88, 1.44] | 1.15 [0.98, 1.41] |
| `objectscript-list-patterns` | IMP-0052               | 17    | 0              | 2              | 17 / 15              | 1        | 0.72 [0.47, 1.15] | 0.86 [0.59, 1.29] |
| `iris-sql`                   | IMP-0054               | 15    | 0              | 0              | 15 / 15              | 0        | 1.08 [1.00, 1.16] | 1.29 [1.16, 1.45] |

**No skill is net positive on luna.** The skill arm never won a pair that tools lost. In four skills tools
won one or two pairs that the skill arm lost. The `objectscript-guardrails` completion win from the
first study did not appear and did not replicate: 0 against 0 in the first luna run and 0 against 2 in the
second. Calls are a little lower with the skill in some skills (`objectscript-sql-patterns` has a calls ratio
interval of 0.78 to 0.98) and cost is level or higher; none meets the efficiency criterion, which needs a
cost ratio of at most 0.80.

The reason is a ceiling. Luna at high effort passed every usable pair with the tools alone (132 of 132);
the skill arm passed 125 of 132. There is nothing for a skill to add. The gpt-4.1 effect (9 of 21
passing with tools alone, 19 with the skill) was a weak-model effect: a skill helps when the agent would
otherwise miss the fact. These tasks are written from the skills' own facts, and a stronger model knows
them or finds them from the compiler. A fair test of a skill needs tasks where the baseline fails
sometimes.

What the infrastructure cost, so the next reader does not repeat it:

- Two earlier attempts at parallel runs were invalid and are voided in the ledger (IMP-0020 to 0025, 0028,
  0036, 0043). The task prompts name `iris-dev-iris` and its port, so an agent in a worker lane edited the
  main container; and the iad server could see 32 registered servers and an agent picked one by name.
  Fixed by rewriting the container and port in each prompt per lane and giving the iad server an empty
  config home.
- The iad MCP server did not answer in about one session in five while the host's load average was near 38.
  Such a session is unscored, and is run again up to twice. Of the 550 luna sessions written (voided runs
  included), 121 were run more than once. I could not reproduce the hang outside the ladder; the load is the likeliest cause.
- Spend on the second study so far is about $5 for 8 skill runs, against about $237 for the seven runs of the
  first study. Sessions cost $0.00 to $0.05.

## Third study: gpt-oss-120b on Bedrock, default effort

Luna's ceiling left no room for a skill, so I looked for a model whose baseline fails sometimes. I ran the
tools arm alone on the train tasks only (7 tasks, 3 repeats) on two open-weight models and chose the one that
passes about half: `gpt-oss-120b` passed 10 of 18, `gpt-oss-20b` 3 of 18. Held-out tasks were not used to
choose. The model is `bedrock-compat/openai.gpt-oss-120b-1:0` through Bedrock's chat-completions route,
because it does not answer on the Responses route the luna runs use. Reasoning effort is not wired on this
route, so it runs at its default, and the runs say so. Prices are the usual list rates ($0.15 in, $0.60 out
per million tokens), not checked against Bedrock's own. `ensemble-production` was left out: its train task
needs Interoperability, which the worker containers lack.

| Skill                        | Run                    | Pairs | Only skill (b) | Only tools (c) | Passes tools / skill | Skill loaded | Cost ratio        | Verdict                                    |
| ---------------------------- | ---------------------- | ----- | -------------- | -------------- | -------------------- | ------------ | ----------------- | ------------------------------------------ |
| `objectscript-list-patterns` | IMP-0071               | 17    | 9              | 0              | 1 / 10               | 94%          | 0.94 [0.72, 1.33] | first run qualifies                        |
| `objectscript-list-patterns` | IMP-0076 (replication) | 17    | 10             | 1              | 1 / 10               | 94%          | 1.16 [0.94, 1.74] | meets criterion 1 and 2a                   |
| `objectscript-list-patterns` | pooled                 | 34    | 19             | 1              |                      |              |                   | **net positive (completion), replicated**  |
| `iris-query-plans`           | IMP-0069               | 14    | 5              | 1              | 6 / 10               | 93%          | 2.02 [1.38, 3.93] | first run qualifies                        |
| `iris-query-plans`           | IMP-0075 (replication) | 15    | 3              | 1              | 7 / 9                | 100%         | 1.69 [1.33, 2.29] | not net positive                           |
| `iris-query-plans`           | pooled                 | 29    | 8              | 2              |                      |              |                   | **not net positive** (two losses)          |
| `objectscript-sql-patterns`  | IMP-0070               | 17    | 8              | 2              | 6 / 12               | 94%          | 0.97 [0.82, 1.23] | not net positive (two losses)              |
| `objectscript-guardrails`    | IMP-0067               | 19    | 5              | 2              | 6 / 9                | 90%          | 0.79 [0.50, 1.25] | not net positive (two losses)              |
| `objectscript-guardrails`    | IMP-0068               | 16    | 5              | 1              | 5 / 9                | 81%          | 1.52 [1.07, 2.24] | no verdict (loaded under 90%)              |
| `iris-agentic-dev`           | IMP-0072               | 15    | 1              | 0              | 14 / 15              | 100%         | 1.28 [0.77, 2.10] | not net positive                           |
| `objectscript-tdd`           | IMP-0074               | 12    | 2              | 0              | 9 / 11               | 80%          | 0.89 [0.56, 2.17] | no verdict (loaded under 90%)              |
| `iris-sql`                   | IMP-0073               | 0     |                |                |                      |              |                   | aborted: worker 3's IRIS stopped answering |
| `iris-sql`                   | IMP-0077               | 13    | 2              | 1              | 1 / 2                | 87%          | 1.04 [0.87, 1.35] | no verdict (loaded under 90%)              |

**`objectscript-list-patterns` is net positive.** Tools alone passed 1 of 17 pairs in each run, so the
baseline is very weak, and the skill arm passed 10 of 17 in each. The first run had 9 wins and no losses; the
second 10 wins and 1 loss. Each meets criterion 1, the pooled data hold b minus c of 18 with c of 1
(criterion 2a at its pooled numbers), and criterion 3 is met by the pooled route. The direction route would
not have held on its own, so the pooled route carries it. Cost is level: ratios 0.94 and 1.16, intervals
containing 1, so there is no efficiency win. It is a completion win only.

The weak baseline matters as much as the skill. This skill's tasks are ones where `gpt-oss-120b` mostly cannot
find the answer without the fact, and the `$LISTNEXT`, empty-element and removal-order facts are in the
skill. The same skill did nothing on gpt-4.1 (5 against 2 pairs) or luna (0 against 2).

**`iris-query-plans` did not replicate.** The first run qualified (5 wins, 1 loss), the second did not (3
wins, 1 loss), and the pooled data carry two losses where the bar allows one. The skill arm also cost 1.7 to
2.0 times the tools arm.

Two skills (`objectscript-tdd`, `objectscript-guardrails` run 2) had no verdict because this model did not
load the skill in 80% and 81% of treated sessions, under the 90% loading rule. Those pairs are excluded and
reported, not counted as failures. `iris-sql` has no verdict for the same reason.

### The pooled tools ladder on luna

The shape 121 measured on gpt-4.1: `tools` against `tools+skills`, every skill installed and none preloaded,
over the 41 holdout tools-corpus tasks, 3 repeats, gpt-6-luna high (IMP-0055 to IMP-0058, four shards run in
parallel; `python3 -m tests.e2e.skill_eval.pooled_ladder`). 121 pairs, 2 unscored. Only the skills arm passed
in 3 pairs, only tools in none; passes 118 against 121. The lift is +0.024 with a 95% interval of 0.000 to
+0.057 (mean over tasks of the per-task pass-rate difference). The calls ratio is 1.33 and the cost ratio 1.92.
The agent loaded a skill in 123 of 123 `tools+skills` sessions, where gpt-4.1 loaded one in 0 of 58. So on luna
the lift, if any, is not the skill index alone, and it costs about twice as much.

## Budget

Total measured spend $275.15 of $300: $237.69 on the gpt-4.1 study (IMP-0011 to IMP-0019) and $37.46 on the
Bedrock studies from IMP-0047 on ($6.23 luna, including $2.80 for the four tools-ladder shards; $31.23 for the
open-weight models, of which $0.41 is `gpt-oss-20b`). The ledger events hold every figure. For the gpt-4.1
study: guardrails $54.59, query-plans $48.32, sql-patterns $42.27, agentic-dev $4.82, tdd $11.50,
list-patterns $35.09, iris-sql $41.10; a session cost $0.09 to $6.51 and a 30-session run $5 to $48. The
per-run cap ($40) stopped two of those runs; the continuation of guardrails (IMP-0012, IMP-0013) finished its
missing 5 sessions from a worktree at the same commit with the same binary sha256 (`3f28647770eb…`).
A session on luna cost under $0.05 and on `gpt-oss-120b` up to $0.25.

Stops at each $50 were reported as they happened for the gpt-4.1 study; the Bedrock studies stayed
under one $50 mark between them.

## What was not done, and why

- **No replication in the gpt-4.1 study.** The only candidate there was `objectscript-guardrails`. Its second
  run would have cost about $50, against $5.41 left in its per-skill cap, so under `criteria.md` it is not net
  positive on gpt-4.1. The Bedrock studies were cheap enough to replicate where a skill qualified.
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

## Deviations in the Bedrock studies

- The model, its prices and its effort are on every session line; reports never pool two models.
- Runs went in parallel on throwaway IRIS containers (one per lane, removed or kept stopped afterwards), with
  each task prompt rewritten to name the lane's container and port, and the iad server given an empty config
  home.
- A session whose iad server never answered is run again, up to twice; its cost still counts. Pairs where the
  skill was not loaded are excluded and reported, per the 90% rule.
- The open-weight models run at default effort because that route cannot carry it.
- Voided runs: IMP-0020 to 0025, 0028, 0036, 0043 (see Second study).

## Stopped

`iris-sql` (IMP-0019) has 2 of 3 repeats and 6 usable pairs. The table below is the partial figure
the report gives, with the verdict "no verdict (fewer than 3 repeats)".

## Tables

One block per skill and per model, from `python3 -m tests.e2e.skill_eval.evidence --markdown`. Rows for the
gpt-4.1 study say so; the model is named on every other row.

### iris-agentic-dev @ openai/gpt-4.1 (the old default; not written on these lines)

Verdict: **not net positive**

Ledger: IMP-0016. Spend $4.82. Model: not recorded (sessions before 135 carry none). Build: 1.5.0 at d39e7cc. Held-out tasks: SKILL-18, SKILL-41, SKILL-42, SKILL-43, SKILL-44. Train runs: 0.

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

### iris-agentic-dev @ bedrock-oai/global.openai.gpt-6-luna high

Verdict: **not net positive**

Ledger: IMP-0049. Spend $0.26. Model: bedrock-oai/global.openai.gpt-6-luna high. Build: 1.5.0 at c68e43b. Held-out tasks: SKILL-18, SKILL-41, SKILL-42, SKILL-43, SKILL-44. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                 | 95% interval   |
| ------------------------------------- | ----------------------------------------------------- | -------------- |
| Usable pairs                          | 15                                                    |                |
| Only the skill passed (b)             | 0                                                     |                |
| Only tools passed (c)                 | 0                                                     |                |
| Skill loaded in treated sessions      | 100%                                                  |                |
| Unloaded / unscored pairs             | 0 / 0                                                 |                |
| Calls ratio (treated / tools)         | 0.84                                                  | [0.68, 1.04]   |
| Calls difference per pair             | -1.4                                                  | [-3.1, +0.3]   |
| Cost ratio (treated / tools)          | 1.76                                                  | [1.63, 1.95]   |
| Cost difference per pair (USD)        | +0.00                                                 | [+0.00, +0.00] |
| Tasks where the treated arm cost less | 0%                                                    |                |
| Tokens, tools                         | in 192,897, out 7,305, cache read 2,481,092 / write 0 |                |
| Tokens, treated                       | in 542,744, out 7,442, cache read 2,942,601 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### iris-agentic-dev @ bedrock-compat/openai.gpt-oss-120b-1:0 default effort

Verdict: **not net positive**

Ledger: IMP-0072. Spend $1.20. Model: bedrock-compat/openai.gpt-oss-120b-1:0 default effort. Build: 1.5.0 at 0e39372. Held-out tasks: SKILL-18, SKILL-41, SKILL-42, SKILL-43, SKILL-44. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 15                                                     |                |
| Only the skill passed (b)             | 1                                                      |                |
| Only tools passed (c)                 | 0                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 0                                                  |                |
| Calls ratio (treated / tools)         | 1.13                                                   | [0.70, 1.83]   |
| Calls difference per pair             | +0.9                                                   | [-2.9, +4.5]   |
| Cost ratio (treated / tools)          | 1.28                                                   | [0.77, 2.10]   |
| Cost difference per pair (USD)        | +0.01                                                  | [-0.01, +0.03] |
| Tasks where the treated arm cost less | 40%                                                    |                |
| Tokens, tools                         | in 3,308,738, out 26,332, cache read 704,848 / write 0 |                |
| Tokens, treated                       | in 4,261,404, out 26,275, cache read 677,136 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### iris-query-plans @ openai/gpt-4.1 (the old default; not written on these lines)

Verdict: **not net positive**

Ledger: IMP-0014. Spend $48.32. Model: not recorded (sessions before 135 carry none). Build: 1.5.0 at 8e92d72. Held-out tasks: SKILL-20, SKILL-33, SKILL-34, SKILL-35, SKILL-36. Train runs: 0.

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

### iris-query-plans @ bedrock-oai/global.openai.gpt-6-luna high

Verdict: **not net positive**

Ledger: IMP-0048. Spend $0.50. Model: bedrock-oai/global.openai.gpt-6-luna high. Build: 1.5.0 at c68e43b. Held-out tasks: SKILL-20, SKILL-33, SKILL-34, SKILL-35, SKILL-36. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 14                                                     |                |
| Only the skill passed (b)             | 0                                                      |                |
| Only tools passed (c)                 | 1                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 1                                                  |                |
| Calls ratio (treated / tools)         | 0.93                                                   | [0.64, 1.39]   |
| Calls difference per pair             | -2.3                                                   | [-9.9, +6.5]   |
| Cost ratio (treated / tools)          | 1.01                                                   | [0.78, 1.27]   |
| Cost difference per pair (USD)        | -0.00                                                  | [-0.00, +0.00] |
| Tasks where the treated arm cost less | 60%                                                    |                |
| Tokens, tools                         | in 518,633, out 21,211, cache read 5,282,872 / write 0 |                |
| Tokens, treated                       | in 572,988, out 21,231, cache read 4,992,027 / write 0 |                |

Criteria on this run: 1 False, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### iris-query-plans @ bedrock-compat/openai.gpt-oss-120b-1:0 default effort

Verdict: **not net positive**

Ledger: IMP-0064, IMP-0069, IMP-0075. Spend $6.01. Model: bedrock-compat/openai.gpt-oss-120b-1:0 default effort. Build: 1.5.0 at 0e39372. Held-out tasks: SKILL-20, SKILL-33, SKILL-34, SKILL-35, SKILL-36. Train runs: 1.

Run 1: first run qualifies, awaiting replication

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 14                                                        |                |
| Only the skill passed (b)             | 5                                                         |                |
| Only tools passed (c)                 | 1                                                         |                |
| Skill loaded in treated sessions      | 93%                                                       |                |
| Unloaded / unscored pairs             | 1 / 0                                                     |                |
| Calls ratio (treated / tools)         | 1.85                                                      | [1.24, 3.44]   |
| Calls difference per pair             | +10.6                                                     | [+3.9, +19.5]  |
| Cost ratio (treated / tools)          | 2.02                                                      | [1.38, 3.93]   |
| Cost difference per pair (USD)        | +0.07                                                     | [+0.03, +0.11] |
| Tasks where the treated arm cost less | 0%                                                        |                |
| Tokens, tools                         | in 6,089,440, out 33,006, cache read 1,197,040 / write 0  |                |
| Tokens, treated                       | in 12,341,331, out 62,820, cache read 2,172,016 / write 0 |                |

Criteria on this run: 1 True, 2a True, 2b False, 2c False. Left out: thin -, not held out -.

Run 2: not net positive

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 15                                                        |                |
| Only the skill passed (b)             | 3                                                         |                |
| Only tools passed (c)                 | 1                                                         |                |
| Skill loaded in treated sessions      | 100%                                                      |                |
| Unloaded / unscored pairs             | 0 / 0                                                     |                |
| Calls ratio (treated / tools)         | 1.42                                                      | [1.11, 1.90]   |
| Calls difference per pair             | +6.9                                                      | [+2.2, +11.1]  |
| Cost ratio (treated / tools)          | 1.69                                                      | [1.33, 2.29]   |
| Cost difference per pair (USD)        | +0.05                                                     | [+0.03, +0.07] |
| Tasks where the treated arm cost less | 0%                                                        |                |
| Tokens, tools                         | in 7,090,416, out 45,889, cache read 2,477,056 / write 0  |                |
| Tokens, treated                       | in 12,065,844, out 63,683, cache read 2,502,784 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

Replication: pooled route False, direction route False, kinds replicated none.

### iris-sql @ openai/gpt-4.1 (the old default; not written on these lines)

Verdict: **no verdict (fewer than 3 repeats (2))**

Ledger: IMP-0019. Spend $41.10. Model: not recorded (sessions before 135 carry none). Build: 1.5.0 at 11d0808. Held-out tasks: SKILL-11, SKILL-48, SKILL-49, SKILL-50, SKILL-51. Train runs: 0.

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

### iris-sql @ bedrock-oai/global.openai.gpt-6-luna high

Verdict: **not net positive**

Ledger: IMP-0054. Spend $0.39. Model: bedrock-oai/global.openai.gpt-6-luna high. Build: 1.5.0 at 0a79505. Held-out tasks: SKILL-11, SKILL-48, SKILL-49, SKILL-50, SKILL-51. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 15                                                     |                |
| Only the skill passed (b)             | 0                                                      |                |
| Only tools passed (c)                 | 0                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 0                                                  |                |
| Calls ratio (treated / tools)         | 1.08                                                   | [1.00, 1.16]   |
| Calls difference per pair             | +1.2                                                   | [-0.1, +2.5]   |
| Cost ratio (treated / tools)          | 1.29                                                   | [1.16, 1.45]   |
| Cost difference per pair (USD)        | +0.00                                                  | [+0.00, +0.00] |
| Tasks where the treated arm cost less | 0%                                                     |                |
| Tokens, tools                         | in 348,316, out 21,945, cache read 5,136,330 / write 0 |                |
| Tokens, treated                       | in 635,536, out 22,709, cache read 6,025,509 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### iris-sql @ bedrock-compat/openai.gpt-oss-120b-1:0 default effort

Verdict: **no verdict (fewer than 3 repeats (2))**

Ledger: IMP-0073, IMP-0077. Spend $4.64. Model: bedrock-compat/openai.gpt-oss-120b-1:0 default effort. Build: 1.5.0 at 0e39372. Held-out tasks: SKILL-11, SKILL-48, SKILL-49, SKILL-50, SKILL-51. Train runs: 0.

Run 1: no verdict (fewer than 3 repeats (2))

| Measure                          | Value | 95% interval |
| -------------------------------- | ----- | ------------ |
| Usable pairs                     | 0     |              |
| Only the skill passed (b)        | 0     |              |
| Only tools passed (c)            | 0     |              |
| Skill loaded in treated sessions | 100%  |              |
| Unloaded / unscored pairs        | 0 / 2 |              |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin {'SKILL-11': 1, 'SKILL-48': 1, 'SKILL-49': 1, 'SKILL-50': 1, 'SKILL-51': 1}, not held out -.

Run 2: no verdict (the skill was loaded in 87% of treated sessions, under 90%)

| Measure                               | Value                                                    | 95% interval   |
| ------------------------------------- | -------------------------------------------------------- | -------------- |
| Usable pairs                          | 13                                                       |                |
| Only the skill passed (b)             | 2                                                        |                |
| Only tools passed (c)                 | 1                                                        |                |
| Skill loaded in treated sessions      | 87%                                                      |                |
| Unloaded / unscored pairs             | 2 / 0                                                    |                |
| Calls ratio (treated / tools)         | 0.74                                                     | [0.57, 1.02]   |
| Calls difference per pair             | -7.0                                                     | [-14.4, +0.0]  |
| Cost ratio (treated / tools)          | 1.04                                                     | [0.87, 1.35]   |
| Cost difference per pair (USD)        | +0.00                                                    | [-0.02, +0.03] |
| Tasks where the treated arm cost less | 60%                                                      |                |
| Tokens, tools                         | in 9,063,878, out 77,586, cache read 3,677,024 / write 0 |                |
| Tokens, treated                       | in 9,504,172, out 63,383, cache read 1,482,992 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-guardrails @ openai/gpt-4.1 (the old default; not written on these lines)

Verdict: **first run qualifies, awaiting replication** (completion)

Ledger: IMP-0011, IMP-0012, IMP-0013. Spend $54.59. Model: not recorded (sessions before 135 carry none). Build: 1.5.0 at bd53cd5. Held-out tasks: SKILL-01, SKILL-04, SKILL-17, SKILL-26, SKILL-27, SKILL-28, SKILL-29. Train runs: 0.

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

### objectscript-guardrails @ bedrock-oai/global.openai.gpt-6-luna high

Verdict: **not net positive**

Ledger: IMP-0047, IMP-0050. Spend $0.96. Model: bedrock-oai/global.openai.gpt-6-luna high. Build: 1.5.0 at c68e43b. Held-out tasks: SKILL-01, SKILL-04, SKILL-17, SKILL-26, SKILL-27, SKILL-28, SKILL-29. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 20                                                     |                |
| Only the skill passed (b)             | 0                                                      |                |
| Only tools passed (c)                 | 0                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 1                                                  |                |
| Calls ratio (treated / tools)         | 0.81                                                   | [0.57, 1.16]   |
| Calls difference per pair             | -2.8                                                   | [-7.3, +1.3]   |
| Cost ratio (treated / tools)          | 0.88                                                   | [0.62, 1.30]   |
| Cost difference per pair (USD)        | -0.00                                                  | [-0.00, +0.00] |
| Tasks where the treated arm cost less | 29%                                                    |                |
| Tokens, tools                         | in 467,343, out 29,598, cache read 6,560,633 / write 0 |                |
| Tokens, treated                       | in 515,751, out 21,699, cache read 5,096,089 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

Run 2: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 21                                                     |                |
| Only the skill passed (b)             | 0                                                      |                |
| Only tools passed (c)                 | 2                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 0                                                  |                |
| Calls ratio (treated / tools)         | 0.79                                                   | [0.53, 1.14]   |
| Calls difference per pair             | -3.0                                                   | [-8.5, +1.3]   |
| Cost ratio (treated / tools)          | 0.94                                                   | [0.67, 1.25]   |
| Cost difference per pair (USD)        | -0.00                                                  | [-0.00, +0.00] |
| Tasks where the treated arm cost less | 29%                                                    |                |
| Tokens, tools                         | in 647,829, out 30,895, cache read 6,657,560 / write 0 |                |
| Tokens, treated                       | in 656,248, out 24,892, cache read 5,843,756 / write 0 |                |

Criteria on this run: 1 False, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-guardrails @ bedrock-compat/openai.gpt-oss-120b-1:0 default effort

Verdict: **not net positive**

Ledger: IMP-0059, IMP-0067, IMP-0068. Spend $7.86. Model: bedrock-compat/openai.gpt-oss-120b-1:0 default effort. Build: 1.5.0 at 0e39372. Held-out tasks: SKILL-01, SKILL-04, SKILL-17, SKILL-26, SKILL-27, SKILL-28, SKILL-29. Train runs: 1.

Run 1: not net positive

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 19                                                        |                |
| Only the skill passed (b)             | 5                                                         |                |
| Only tools passed (c)                 | 2                                                         |                |
| Skill loaded in treated sessions      | 90%                                                       |                |
| Unloaded / unscored pairs             | 2 / 0                                                     |                |
| Calls ratio (treated / tools)         | 0.81                                                      | [0.51, 1.29]   |
| Calls difference per pair             | -3.3                                                      | [-12.8, +4.0]  |
| Cost ratio (treated / tools)          | 0.79                                                      | [0.50, 1.25]   |
| Cost difference per pair (USD)        | -0.02                                                     | [-0.07, +0.02] |
| Tasks where the treated arm cost less | 57%                                                       |                |
| Tokens, tools                         | in 13,309,636, out 89,110, cache read 3,433,536 / write 0 |                |
| Tokens, treated                       | in 10,413,184, out 79,549, cache read 3,127,168 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

Run 2: no verdict (the skill was loaded in 81% of treated sessions, under 90%)

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 16                                                        |                |
| Only the skill passed (b)             | 5                                                         |                |
| Only tools passed (c)                 | 1                                                         |                |
| Skill loaded in treated sessions      | 81%                                                       |                |
| Unloaded / unscored pairs             | 4 / 0                                                     |                |
| Calls ratio (treated / tools)         | 1.69                                                      | [1.12, 2.58]   |
| Calls difference per pair             | +7.6                                                      | [+1.3, +15.7]  |
| Cost ratio (treated / tools)          | 1.52                                                      | [1.07, 2.24]   |
| Cost difference per pair (USD)        | +0.03                                                     | [+0.00, +0.07] |
| Tasks where the treated arm cost less | 33%                                                       |                |
| Tokens, tools                         | in 6,752,742, out 38,763, cache read 1,211,088 / write 0  |                |
| Tokens, treated                       | in 10,179,527, out 73,682, cache read 2,730,432 / write 0 |                |

Criteria on this run: 1 True, 2a True, 2b False, 2c False. Left out: thin {'SKILL-29': 1}, not held out -.

### objectscript-list-patterns @ openai/gpt-4.1 (the old default; not written on these lines)

Verdict: **not net positive**

Ledger: IMP-0018. Spend $35.09. Model: not recorded (sessions before 135 carry none). Build: 1.5.0 at 13b02f4. Held-out tasks: SKILL-06, SKILL-07, SKILL-10, SKILL-45, SKILL-46, SKILL-47. Train runs: 0.

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

### objectscript-list-patterns @ bedrock-oai/global.openai.gpt-6-luna high

Verdict: **not net positive**

Ledger: IMP-0052. Spend $0.40. Model: bedrock-oai/global.openai.gpt-6-luna high. Build: 1.5.0 at c68e43b. Held-out tasks: SKILL-06, SKILL-07, SKILL-10, SKILL-45, SKILL-46, SKILL-47. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 17                                                     |                |
| Only the skill passed (b)             | 0                                                      |                |
| Only tools passed (c)                 | 2                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 1                                                  |                |
| Calls ratio (treated / tools)         | 0.72                                                   | [0.47, 1.15]   |
| Calls difference per pair             | -3.3                                                   | [-8.0, +1.1]   |
| Cost ratio (treated / tools)          | 0.86                                                   | [0.59, 1.29]   |
| Cost difference per pair (USD)        | -0.00                                                  | [-0.00, +0.00] |
| Tasks where the treated arm cost less | 50%                                                    |                |
| Tokens, tools                         | in 390,399, out 19,498, cache read 4,517,538 / write 0 |                |
| Tokens, treated                       | in 475,730, out 12,729, cache read 3,304,595 / write 0 |                |

Criteria on this run: 1 False, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-list-patterns @ bedrock-compat/openai.gpt-oss-120b-1:0 default effort

Verdict: **net positive** (completion)

Ledger: IMP-0071, IMP-0076. Spend $4.80. Model: bedrock-compat/openai.gpt-oss-120b-1:0 default effort. Build: 1.5.0 at 0e39372. Held-out tasks: SKILL-06, SKILL-07, SKILL-10, SKILL-45, SKILL-46, SKILL-47. Train runs: 0.

Run 1: first run qualifies, awaiting replication

| Measure                               | Value                                                    | 95% interval   |
| ------------------------------------- | -------------------------------------------------------- | -------------- |
| Usable pairs                          | 17                                                       |                |
| Only the skill passed (b)             | 9                                                        |                |
| Only tools passed (c)                 | 0                                                        |                |
| Skill loaded in treated sessions      | 94%                                                      |                |
| Unloaded / unscored pairs             | 1 / 0                                                    |                |
| Calls ratio (treated / tools)         | 0.93                                                     | [0.68, 1.44]   |
| Calls difference per pair             | -1.6                                                     | [-6.9, +4.2]   |
| Cost ratio (treated / tools)          | 0.94                                                     | [0.72, 1.33]   |
| Cost difference per pair (USD)        | -0.01                                                    | [-0.03, +0.02] |
| Tasks where the treated arm cost less | 67%                                                      |                |
| Tokens, tools                         | in 8,110,123, out 55,320, cache read 1,623,312 / write 0 |                |
| Tokens, treated                       | in 7,717,798, out 31,468, cache read 1,150,416 / write 0 |                |

Criteria on this run: 1 True, 2a True, 2b False, 2c False. Left out: thin -, not held out -.

Run 2: first run qualifies, awaiting replication

| Measure                               | Value                                                    | 95% interval   |
| ------------------------------------- | -------------------------------------------------------- | -------------- |
| Usable pairs                          | 17                                                       |                |
| Only the skill passed (b)             | 10                                                       |                |
| Only tools passed (c)                 | 1                                                        |                |
| Skill loaded in treated sessions      | 94%                                                      |                |
| Unloaded / unscored pairs             | 1 / 0                                                    |                |
| Calls ratio (treated / tools)         | 1.01                                                     | [0.78, 1.58]   |
| Calls difference per pair             | +0.9                                                     | [-3.2, +6.6]   |
| Cost ratio (treated / tools)          | 1.16                                                     | [0.94, 1.74]   |
| Cost difference per pair (USD)        | +0.01                                                    | [-0.00, +0.03] |
| Tasks where the treated arm cost less | 33%                                                      |                |
| Tokens, tools                         | in 6,198,541, out 42,128, cache read 2,366,544 / write 0 |                |
| Tokens, treated                       | in 7,227,303, out 36,342, cache read 1,409,520 / write 0 |                |

Criteria on this run: 1 True, 2a True, 2b False, 2c False. Left out: thin -, not held out -.

Replication: pooled route True, direction route False, kinds replicated completion.

### objectscript-sql-patterns @ openai/gpt-4.1 (the old default; not written on these lines)

Verdict: **not net positive**

Ledger: IMP-0015. Spend $42.27. Model: not recorded (sessions before 135 carry none). Build: 1.5.0 at 03022af. Held-out tasks: SKILL-08, SKILL-12, SKILL-15, SKILL-30, SKILL-31, SKILL-32. Train runs: 0.

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

### objectscript-sql-patterns @ bedrock-oai/global.openai.gpt-6-luna high

Verdict: **not net positive**

Ledger: IMP-0053. Spend $0.57. Model: bedrock-oai/global.openai.gpt-6-luna high. Build: 1.5.0 at c68e43b. Held-out tasks: SKILL-08, SKILL-12, SKILL-15, SKILL-30, SKILL-31, SKILL-32. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                  | 95% interval   |
| ------------------------------------- | ------------------------------------------------------ | -------------- |
| Usable pairs                          | 17                                                     |                |
| Only the skill passed (b)             | 0                                                      |                |
| Only tools passed (c)                 | 1                                                      |                |
| Skill loaded in treated sessions      | 100%                                                   |                |
| Unloaded / unscored pairs             | 0 / 1                                                  |                |
| Calls ratio (treated / tools)         | 0.89                                                   | [0.78, 0.98]   |
| Calls difference per pair             | -1.5                                                   | [-3.3, +0.0]   |
| Cost ratio (treated / tools)          | 1.09                                                   | [0.95, 1.32]   |
| Cost difference per pair (USD)        | +0.00                                                  | [-0.00, +0.00] |
| Tasks where the treated arm cost less | 50%                                                    |                |
| Tokens, tools                         | in 447,732, out 19,107, cache read 4,779,469 / write 0 |                |
| Tokens, treated                       | in 595,422, out 17,608, cache read 4,476,044 / write 0 |                |

Criteria on this run: 1 False, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-sql-patterns @ bedrock-compat/openai.gpt-oss-120b-1:0 default effort

Verdict: **not net positive**

Ledger: IMP-0061, IMP-0070. Spend $4.93. Model: bedrock-compat/openai.gpt-oss-120b-1:0 default effort. Build: 1.5.0 at 0e39372. Held-out tasks: SKILL-08, SKILL-12, SKILL-15, SKILL-30, SKILL-31, SKILL-32. Train runs: 1.

Run 1: not net positive

| Measure                               | Value                                                     | 95% interval   |
| ------------------------------------- | --------------------------------------------------------- | -------------- |
| Usable pairs                          | 17                                                        |                |
| Only the skill passed (b)             | 8                                                         |                |
| Only tools passed (c)                 | 2                                                         |                |
| Skill loaded in treated sessions      | 94%                                                       |                |
| Unloaded / unscored pairs             | 1 / 0                                                     |                |
| Calls ratio (treated / tools)         | 0.91                                                      | [0.75, 1.16]   |
| Calls difference per pair             | -1.7                                                      | [-6.6, +3.1]   |
| Cost ratio (treated / tools)          | 0.97                                                      | [0.82, 1.23]   |
| Cost difference per pair (USD)        | -0.00                                                     | [-0.03, +0.02] |
| Tasks where the treated arm cost less | 33%                                                       |                |
| Tokens, tools                         | in 13,210,727, out 87,735, cache read 2,743,600 / write 0 |                |
| Tokens, treated                       | in 12,909,463, out 75,648, cache read 2,255,616 / write 0 |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-tdd @ openai/gpt-4.1 (the old default; not written on these lines)

Verdict: **not net positive**

Ledger: IMP-0017. Spend $11.50. Model: not recorded (sessions before 135 carry none). Build: 1.5.0 at b59b9cc. Held-out tasks: SKILL-19, SKILL-37, SKILL-38, SKILL-39, SKILL-40. Train runs: 0.

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

### objectscript-tdd @ bedrock-oai/global.openai.gpt-6-luna high

Verdict: **not net positive**

Ledger: IMP-0051. Spend $0.35. Model: bedrock-oai/global.openai.gpt-6-luna high. Build: 1.5.0 at c68e43b. Held-out tasks: SKILL-19, SKILL-37, SKILL-38, SKILL-39, SKILL-40. Train runs: 0.

Run 1: not net positive

| Measure                               | Value                                                 | 95% interval   |
| ------------------------------------- | ----------------------------------------------------- | -------------- |
| Usable pairs                          | 13                                                    |                |
| Only the skill passed (b)             | 0                                                     |                |
| Only tools passed (c)                 | 1                                                     |                |
| Skill loaded in treated sessions      | 100%                                                  |                |
| Unloaded / unscored pairs             | 0 / 2                                                 |                |
| Calls ratio (treated / tools)         | 1.05                                                  | [0.88, 1.44]   |
| Calls difference per pair             | +0.7                                                  | [-1.3, +3.0]   |
| Cost ratio (treated / tools)          | 1.15                                                  | [0.98, 1.41]   |
| Cost difference per pair (USD)        | +0.00                                                 | [-0.00, +0.00] |
| Tasks where the treated arm cost less | 20%                                                   |                |
| Tokens, tools                         | in 294,676, out 7,992, cache read 1,823,105 / write 0 |                |
| Tokens, treated                       | in 331,158, out 8,241, cache read 2,494,361 / write 0 |                |

Criteria on this run: 1 False, 2a False, 2b False, 2c False. Left out: thin -, not held out -.

### objectscript-tdd @ bedrock-compat/openai.gpt-oss-120b-1:0 default effort

Verdict: **no verdict (the skill was loaded in 80% of treated sessions, under 90%)**

Ledger: IMP-0074. Spend $1.38. Model: bedrock-compat/openai.gpt-oss-120b-1:0 default effort. Build: 1.5.0 at 0e39372. Held-out tasks: SKILL-19, SKILL-37, SKILL-38, SKILL-39, SKILL-40. Train runs: 0.

Run 1: no verdict (the skill was loaded in 80% of treated sessions, under 90%)

| Measure                               | Value                                                    | 95% interval   |
| ------------------------------------- | -------------------------------------------------------- | -------------- |
| Usable pairs                          | 12                                                       |                |
| Only the skill passed (b)             | 2                                                        |                |
| Only tools passed (c)                 | 0                                                        |                |
| Skill loaded in treated sessions      | 80%                                                      |                |
| Unloaded / unscored pairs             | 3 / 0                                                    |                |
| Calls ratio (treated / tools)         | 0.82                                                     | [0.53, 2.11]   |
| Calls difference per pair             | -1.7                                                     | [-8.3, +3.4]   |
| Cost ratio (treated / tools)          | 0.89                                                     | [0.56, 2.17]   |
| Cost difference per pair (USD)        | -0.00                                                    | [-0.04, +0.02] |
| Tasks where the treated arm cost less | 40%                                                      |                |
| Tokens, tools                         | in 4,104,139, out 21,722, cache read 1,157,200 / write 0 |                |
| Tokens, treated                       | in 3,647,900, out 16,105, cache read 703,344 / write 0   |                |

Criteria on this run: 1 True, 2a False, 2b False, 2c False. Left out: thin -, not held out -.
