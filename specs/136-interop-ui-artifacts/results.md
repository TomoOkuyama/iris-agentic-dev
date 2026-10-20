# 136 results

A correctness check, with no net-positive claim (Q4). Arms `tools` and `tools+ensemble-production`, the
held-out tasks SKILL-67 (rewrite a code-based process and its rules as BPL and a rule class, behaviour
kept), SKILL-68 (a DTL) and SKILL-69 (a routing rule), 3 repeats, on build 1.5.0 `6fc3321` (binary
sha256 `7c4e29de1375`), against `iris-dev-iris` BENCHMARK. Spend $2.71 measured of the $5 cap.

## gpt-oss-120b (Bedrock, default effort)

Run files `ladder-20261017T153014`, `ladder-20261018T165457`, `ladder-20261020T090433`,
`ladder-20261020T090922`. Spend $2.30.

| Task     | tools  | tools+ensemble-production | skill loaded |
| -------- | ------ | ------------------------- | ------------ |
| SKILL-67 | 0 of 2 | 0 of 3                    | 3 of 3       |
| SKILL-68 | 0 of 3 | 2 of 3                    | 3 of 3       |
| SKILL-69 | 0 of 3 | 0 of 3                    | 3 of 3       |
| All      | 0 of 8 | 2 of 9                    | 9 of 9       |

SC-001 (the skill arm passes each task in at least 2 of 3) holds for SKILL-68 only. On this model the
skill turns a DTL task from never solved into mostly solved, and does not get the agent through the
lookalike or the routing rule.

Unscored, and why: repeat 2 of the first run, six sessions with 0 calls and a 300 s timeout each, when the
model endpoint stopped answering (the same connection drop ended my session at the time); repeat 2 was run
again in the second run. Two tools-arm sessions with 0 calls, one when `iris-dev-iris` went down with the
host (SKILL-69, re-run in `ladder-20261020T090433`) and one that ended in 5 s with no call (SKILL-67,
repeat 3). The harness wrote all of them as FAIL; this table does not count them.

## gpt-6-luna (Bedrock, high effort)

Run file `ladder-20261020T092344`. Spend $0.41.

| Task     | tools  | tools+ensemble-production | calls, tools against skill arm  |
| -------- | ------ | ------------------------- | ------------------------------- |
| SKILL-67 | 3 of 3 | 3 of 3                    | 103, 113, 58 against 50, 41, 43 |
| SKILL-68 | 3 of 3 | 2 of 3                    | 14, 19, 18 against 14, 11, 6    |
| SKILL-69 | 2 of 3 | 2 of 2                    | 77, 57, 58 against 29, 42       |
| All      | 8 of 9 | 7 of 8                    |                                 |

The strong model writes BPL, DTL and rule classes without the skill when the prompt says the analysts
use the editors. With the skill it gets there in fewer calls on the lookalike (50, 41 and 43 against 103,
113 and 58) and the routing rule. That is a reading of three repeats, not a measured efficiency claim:
criteria.md's interval test was not run.

Unscored: SKILL-69 skill arm repeat 2, where the iad server answered no call in three attempts. The
SKILL-68 skill-arm FAIL in repeat 3 came on the third attempt after two of the same, with 6 calls in 300 s;
I count it as a fail because the harness scored it, but it is more likely the same server stall than the
skill. IRIS answered queries normally throughout; the cause of the stalls is not known.

## What this does not show

- No net-positive claim, as decided before the run. Three tasks and 3 repeats are below 135's bar.
- The tasks name the editors in the prompt. A prompt that only says "write a business process" was not
  measured; that is where the skill's default matters most, and it is the next task to write.
- Benjamin de Boe's team has not tried the skill on grievance-demo.

## Also found while writing the tasks

- `ensemble-production` taught `##class(Ens.Director).SendRequestSync(...)`, which does not exist (spec 138
  research). The skill now shows an adapterless service's `SendRequestSync`, the route
  `interop_ui_136_facts_the_skill_states` runs.
- `StartProduction` moves the device of the job that calls it, so a script that writes after it loses the
  output unless it saves and restores `$IO`; the skill says so.
- `Case` is a reserved word in IRIS SQL, so a class named `Bench67.Case` compiled but every `&sql` on it
  failed with SQLCODE -1 at run time. The task uses `Bench67.Grievance`.
