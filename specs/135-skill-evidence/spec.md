# Feature Specification: Skill evidence

**Feature Branch**: `135-skill-evidence`
**Created**: 2026-10-10
**Status**: Draft
**Input**: `~/writing/iris-agentic-dev/GOAL-skills-evidence.md`. Show that at least five bundled skills
are net positive, with evidence a hostile reader would accept, or report how many reached that bar
and why the others did not. The bar does not move to reach five.

## Context

Live tools take graded IRIS tasks from 0 of 20 to 20 of 20 on a clean harness. Skills alone score
0 of 18. The old tools-plus-skills lift came from an arm in which no agent loaded a skill (0 of 58).
The clean paired data so far, tools against one preloaded skill, is 48 passes against 52 over 65 pairs
(p=0.61) and the skill arm costs 8 more calls and 0.45 dollars more per session. Every skill starts
presumed not net positive. `objectscript-guardrails` improved on cost after one generic edit; its
held-out tasks SKILL-01, SKILL-04 and SKILL-17 were never run.

## User Scenarios & Testing

### User Story 1 - One command says where each skill stands (P1)

`improve skills` prints, per skill, the paired pass counts, relative calls, cost, tokens, loaded
rate, train and held-out task counts, task-clustered intervals, ledger ids and a verdict against
`criteria.md`. It is derived from the run files and the ledger and stores nothing.

**Independent test**: run files built in a temporary directory with known counts yield the stated b,
c, ratios and verdict; a changed `criteria.md` refuses a verdict.

### User Story 2 - A task can be authored for any skill and proven sound (P1)

`tests/e2e/tasks/skills/<skill>/<TASK>.yaml` holds fixtures, a PASS/FAIL ObjectScript check, a
reference solution, optional `quality_checks`, and its side in `split.toml`. A live test proves the
check false before the solution and true after.

### User Story 3 - A session says what it ran against and what it spent (P1)

Every run record names the binary version, the commit, whether the tree was clean, and per session
the input, output and cache tokens.

### User Story 4 - Measure each candidate skill once, honestly (P1)

For each candidate in order: train tasks, one generic edit if the transcripts support one, then the
held-out tasks once, then a replication run. Results are written down whether they qualify or not.

## Requirements

- **FR-001**: Criteria are committed before the first measurement run; every 135 run event carries
  their sha256; the report refuses a verdict when the file changed.
- **FR-002**: Tokens summed from `step_finish` events are in the run record and the report.
- **FR-003**: `quality_checks` score a fraction beside pass/fail and never replace the main check.
- **FR-004**: A report row names the binary version and commit; a run mixing builds has no verdict.
- **FR-005**: Parallel workers, if any, use one throwaway container each on unregistered ports,
  removed afterwards. Otherwise runs are serial against one container.
- **FR-006**: Spend is the sum of measured cost, with a cap per try, per skill and in total.
- **FR-007**: No skill edit is derived from a held-out transcript. A task read for an edit moves to
  train and the skill needs a fresh held-out task.
- **FR-008**: Every fact a skill edit adds has a live test on IRIS.
