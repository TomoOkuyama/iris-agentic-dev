# Implementation Plan: Interoperability artifacts the editors can open

**Branch**: `feat/improve-cli` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)
**Input**: `spec.md`, `research-docs.md` (facts tagged DOCS, LIVE or UNKNOWN). Runs after 137, which is done.

## Summary

The `ensemble-production` skill gains a section that makes BPL, DTL and rule classes the default for
ObjectScript work and maps each code construct to its editor-visible form. Every fact the section adds is
pinned by a live test on IRIS 2026.2 first. Three new held-out tasks (SKILL-67 lookalike, SKILL-68 DTL,
SKILL-69 routing rule) check that agents produce what the editors open and keep behaviour. A ladder on
`gpt-oss-120b` and `gpt-6-luna` (separate rows) measures it, capped at $5 measured spend. The pyprod limit
is stated only after a live test on a throwaway container.

## Technical Context

**Language/Version**: Markdown (skill), YAML (tasks), Rust 2021 (live tests), Python 3.11 (harness)
**Primary Dependencies**: none new
**Testing**: `cargo test --features testing --test integration test_interop_ui_136 -- --ignored --test-threads=1`
for the facts; the authoring kit's live proof for the tasks; the ladder for the check
**Target Platform**: IRIS 2026.2 on `iris-dev-iris`, BENCHMARK namespace
**Constraints**: skill claims need a live test (FR-005); no edit from held-out transcripts; the split is
fixed before any run; spend capped at $5 measured; `grievance-demo` is not edited or copied

## Constitution Check

| Principle               | Status | Notes                                                                  |
| ----------------------- | ------ | ---------------------------------------------------------------------- |
| II. ObjectScript Sanity | PASS   | every BPL, DTL and rule construct in the skill compiles in a live test |
| IV. Test-First          | PASS   | fact tests before the skill text; task checks proven false then true   |
| IX. Tool Lift           | N/A    | no tool change; the ladder is a correctness check with no lift claim   |
| XI. No Vacuous Tests    | PASS   | each fact test asserts the compile result and the editor API answer    |
| Others                  | N/A    | no binary, schema or dependency change                                 |

## Design

### Facts to pin (one live test each, `tests/integration/test_interop_ui_136_live.rs`)

1. A BPL process with `<context>`, `<call async="0" timeout="5">` inside `<scope>`/`<catchall>`, `<rule>`
   with `resultLocation` and `reasonLocation`, `<assign>` and `<code>` compiles; the BPL editor API
   answers 200; a code-based `Ens.BusinessProcess` gets 400.
2. A general business rule (`Ens.Rule.GeneralBusinessRuleAssist`) whose condition calls a
   `Ens.Rule.FunctionSet` function by bare name compiles and loads through `LoadFromClass`; a qualified
   call does not compile (the docs say otherwise, `research-docs.md` F4).
3. The rule returns its value into `resultLocation`, its `assign` actions add to a context property,
   and `reasonLocation` lists every rule that fired, comma-separated.
4. A DTL class compiles and transforms; the DTL editor API answers 200; a code `Ens.DataTransform` 400.
5. A routing rule (`EnsLib.MsgRouter.RuleAssist`) referenced by a router's `BusinessRuleName` routes.

### Skill section (`skills/skills/ensemble-production/SKILL.md`)

"Write what the editors can open": one paragraph on why, a table code construct → editor form (FR-002),
one compact example each for BPL, DTL and rule class, the read-only rule-function caveat, the `<scope>`
caveat, and when code is acceptable. The existing `OnRequest` gotchas move under "Code-based processes".
A guard test pins the section's facts and a byte cap so the skill does not grow unbounded.

### Tasks (`tests/e2e/tasks/skills/ensemble-production/SKILL-67..69.yaml`)

Holdout from the day they are written. Each has fixtures, a reference solution, a teardown, and a check
that scores structure (superclass, XData block, `LoadFromClass`) and behaviour (fixed inputs through a
running production). The editor API answer is recorded by the check's output, not scored (Q6).

### Ladder

`--side holdout`, tasks SKILL-67 to SKILL-69, arms `tools` and `tools+ensemble-production`, 3 repeats,
`--cap 5` on measured cost, once per model. Results in `results.md` with the loaded rate.

### pyprod limit (US3)

A throwaway container on an unregistered port with pyprod 0.2.0: define a production in Python, load it,
change a setting through `Ens.Director`/the config API as the Portal would, reload from Python, show the
setting is overwritten, and show a System Default Setting survives. Container removed afterwards.

## Project Structure

```text
specs/136-interop-ui-artifacts/{spec,plan,tasks,research-docs,results}.md
crates/iris-agentic-dev-core/tests/integration/test_interop_ui_136_live.rs
crates/iris-agentic-dev-core/tests/unit/test_skill_interop_ui_136.rs
skills/skills/ensemble-production/SKILL.md
tests/e2e/tasks/skills/ensemble-production/SKILL-67.yaml, SKILL-68.yaml, SKILL-69.yaml
tests/e2e/tasks/benchmark/split.toml
```
