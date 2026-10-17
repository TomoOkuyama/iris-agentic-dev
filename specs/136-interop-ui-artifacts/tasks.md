# Tasks: 136 Interoperability artifacts the editors can open

Test first. Live tests on `iris-dev-iris` BENCHMARK, serial.

## Phase 1: Facts (live, before any skill text)

- [ ] T001 `test_interop_ui_136_live.rs` and its `mod` line: facts 1 to 5 of the plan, each compiling
      fixture classes under `IADTest136` and deleting them afterwards

## Phase 2: Skill

- [ ] T010 Guard test `test_skill_interop_ui_136.rs`: the section exists, names the three superclasses
      and XData blocks, the bare-name rule, the read-only caveat, the `<scope>` caveat, code-on-request,
      and the skill stays under its byte cap
- [ ] T011 The section in `ensemble-production/SKILL.md`; existing gotchas moved under "Code-based
      processes"; every fact in it has a test from T001

## Phase 3: Tasks

- [ ] T020 SKILL-68 (DTL) and SKILL-69 (routing rule): fixtures, solution, check, teardown
- [ ] T021 SKILL-67 (lookalike of IntakeBP + Grievance.Rules)
- [ ] T022 `split.toml`: the three on the holdout side, with the reason
- [ ] T023 Live proof through the authoring kit: each check fails on the fixtures and passes on the
      solution

## Phase 4: Measure

- [ ] T030 Ladder on `gpt-oss-120b`, then on `gpt-6-luna` high, `--cap` on measured cost, $5 in total
- [ ] T031 `results.md`: per model, per task, pass by arm, loaded rate, spend; "correctness check, no
      net-positive claim"

## Phase 5: Python

- [ ] T040 Live test of the pyprod overwrite and System Default Settings on a throwaway container
- [ ] T041 The Python section's sentence, only what T040 showed

## Phase 6: Close

- [ ] T050 fmt, clippy, unit, the 136 live tests; markdown linted
- [ ] T051 A note for Benjamin de Boe's team, drafted for Tom to send (nothing sent from here)
