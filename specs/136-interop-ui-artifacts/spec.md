# Feature Specification: Interoperability artifacts the editors can open

**Feature Branch**: `feat/improve-cli` (no branch of its own, like 130 to 135)
**Created**: 2026-10-17
**Status**: Draft
**Input**: Feedback from Benjamin de Boe and the grievance-demo team: "iris-agentic-dev likes creating
code-based BPs and business rules, so we need to turn those into something else for the UI to show
them nicely." Decisions Q1 to Q9 settled with Tom in a grilling session on 2026-10-17. Facts are in
`research-docs.md`, each tagged DOCS, LIVE or UNKNOWN.

**Runs after**: 137 (ObjectScript injection sweep), by Tom's decision (Q9).

## Context

The `ensemble-production` skill teaches business processes only as code: `Ens.BusinessProcess` with
`OnRequest`, its signature gotchas, `OnResponse`. It never mentions BPL (`Ens.BusinessProcessBPL`
with `XData BPL`), DTL (`Ens.DataTransformDTL` with `XData DTL`) or rule classes
(`Ens.Rule.Definition` with `XData RuleDefinition`). The editors open only those three kinds. Their
REST API answers HTTP 400 "is not a BPL business process" for a code-based process and "is not a DTL
data transformation" for a code transform (LIVE). So an agent that follows the skill produces work an
analyst cannot open, and `grievance-demo` shows it: `Grievance.Process.IntakeBP` and `ActionBP`
extend `Ens.BusinessProcess`, and `Grievance.Rules.Evaluate` is a plain class method that runs SQL
and returns `{outcome, reasons[], allowedAction}`.

The tools are not the obstacle. `iris_doc put` with `compile=true` builds a BPL process, including
its generated Context and Thread classes, and a rule class (LIVE, 2026-10-16). The one tool gap,
`iris_business_rule_info` reading only the pre-2012 `Ens.Rule.RuleSet` table, was fixed before this
spec (`6f35d56`), and the 228 test rows it listed were removed (`7ce6433`).

"Show nicely" means the Management Portal's BPL Editor, DTL Editor and Rule Editor, and the newer
editors under `/ui/interop/` (Q1).

## User Scenarios & Testing

### User Story 1 - An agent asked for a process, transform or rule writes one the editors open (P1)

A developer asks for a business process, a data transformation or a routing or business rule in an
ObjectScript project. With `ensemble-production` loaded, the agent writes a BPL class, a DTL class or
a rule class, compiles it, and tells the developer it opens in the editor. It writes a code-based
class only when the developer asks for one, and then says the editor will not open it.

**Independent test**: the DTL task and the routing-rule task (FR-008) pass their structural checks
in the skill arm.

### User Story 2 - An agent converts a code-based process and its rules without changing behaviour (P1)

A developer has a process like `IntakeBP` and rules like `Grievance.Rules` and asks for them to be
editable in the UI. The agent rewrites them: the process as BPL, the decision as a general business
rule, the lookups as read-only rule functions the rule's conditions call, the reasons collected by
the rule's actions, the outcome as the rule's return value, writes kept out of the rule, and the
external call made synchronous with a timeout inside a scope that catches its failure. The same
fixed inputs give the same outcome, queue and reasons as before.

**Independent test**: the lookalike task (FR-008) passes its structural and behaviour checks.

### User Story 3 - A Python developer learns what the UI can and cannot change (P2)

A developer using pyprod asks to change a setting in the Portal. The skill keeps the Python path and
states the limit once: a pyprod production opens in the Portal and the new UI, but edits made there
are overwritten the next time the Python definition loads, and environment-specific values belong in
System Default Settings. Round-trip editing was closed as Won't Do (DP-454977, 2026-09-14).

**Independent test**: a live test on a throwaway container shows the overwrite and the System Default
Settings override before the text ships.

### User Story 4 - The change is checked, not claimed (P2)

A ladder run, tools against tools+`ensemble-production`, 3 repeats, on `gpt-oss-120b` and on
`gpt-6-luna` at high effort as separate rows, says how often each arm produces artifacts that pass.
It stops on measured cost at $5. The results file states that this is a correctness check and makes
no net-positive claim (Q4).

### Edge cases

- The developer asks for a code-based process explicitly: the agent writes it and says the editor
  will not open it.
- A lookup needs to write (an UPDATE guarded by status): it stays out of the rule, in a BPL `<code>`
  step calling a class method or in a business operation. A rule function the Rule Editor's Test
  button runs must be read-only (DOCS).
- Logic with no BPL or rule equivalent (a loop that adds a reason per row, a warning log): a rule
  function or a `<code>` step, named as such, not hidden.
- A `<call>` that fails ends the whole BPL process unless a `<scope>` catches it, unlike the code
  version that carried on (DOCS).
- A rule class with no `RuleAssistClass` still opens, as type "(unknown)"; the skill always sets one.
- The interop-editors REST path is missing or answers differently on another build: recorded, not
  scored (Q6).
- A rule function called by a qualified name fails to compile on 2026.2 although the docs say to
  qualify it (LIVE); the skill uses the bare name and the live test pins it.

## Requirements

### Functional Requirements

- **FR-001**: `ensemble-production` gains a section that makes BPL, DTL and rule classes the default
  for ObjectScript work, with a compact example of each, and says when code-based classes are
  acceptable (the developer asks) and what that costs (no editor).
- **FR-002**: The section maps each code construct to its editor-visible form: synchronous call with
  timeout and `<scope>`; outcome as the rule return into `resultLocation`; reasons through `assign`
  actions on a context property; lookups as read-only `Ens.Rule.FunctionSet` functions called by bare
  name; writes in `<code>` or a business operation (Q5).
- **FR-003**: The existing `OnRequest`/`OnResponse` gotchas stay, under a heading that says they
  apply to code-based processes.
- **FR-004**: The Python section states the pyprod limit (User Story 3) and nothing beyond what the
  live test shows.
- **FR-005**: Every fact the edit adds has a live test on IRIS 2026.2 (`iris-dev-iris`, BENCHMARK),
  in the style of the 130 and 132 content tests; the existing facts keep theirs.
- **FR-006**: The skill stays under its size guard. If the section does not fit, the example moves to
  a reference file the skill names, and the guard test says so.
- **FR-007**: No conversion tool is added (Q2).
- **FR-008**: Three new tasks with fixtures, a reference solution and a check that is false before the
  solution and true after, proven live: (a) the lookalike of `IntakeBP` + `Grievance.Rules` under its
  own package (sync call to a stub business operation with a timeout, missing-member and duplicate
  lookups, a list of reasons, a three-way outcome that picks a queue); (b) a DTL between two message
  classes; (c) a routing rule for a router. Their side in `split.toml` is fixed before any run.
- **FR-009**: The checks score structure and behaviour (Q6): the process extends
  `Ens.BusinessProcessBPL` with `XData BPL`, the transform `Ens.DataTransformDTL` with `XData DTL`,
  the rule `Ens.Rule.Definition` with `XData RuleDefinition` and loads through the rule model; and the
  fixed inputs give the expected outcome, queue and reasons.
- **FR-010**: Each graded session also records the editors' REST answer for each artifact. It is not
  part of the score; a missing path is recorded as missing.
- **FR-011**: The ladder runs both models as separate rows, never pooled, stops on measured cost at $5
  in total, and its results say "correctness check, no net-positive claim".
- **FR-012**: Every class a graded session creates under the fixture packages is deleted afterwards
  (the 130 FR-023 rule).
- **FR-013**: `grievance-demo` is not edited or copied; its team checks it themselves (Q3).

### Key Entities

- **Editor-visible artifact**: a BPL process, a DTL transform or a rule class, each identified by its
  superclass and XData block name.
- **Lookalike task**: the fixture package, a stub business operation, the code-based starting point
  and the fixed inputs with their expected outcome, queue and reasons.

## Success Criteria

- **SC-001**: In the skill arm, on each model, the three tasks pass their structural checks in at
  least 2 of 3 repeats each. Reported for the tools arm beside it, whatever it is.
- **SC-002**: In the lookalike task, every passing session also keeps the behaviour: every fixed input
  gives the expected outcome, queue and reasons.
- **SC-003**: Every claim the skill edit adds has a live test that passes on 2026.2.
- **SC-004**: Spend stays at or under $5 measured.
- **SC-005**: Benjamin de Boe's team has the skill text and the lookalike task to try on
  `grievance-demo` (handed over by Tom; nothing is sent from here).

## Assumptions

- The skill arm loads its skill in at least 90% of sessions, as 135 required; below that, the run is
  reported with its loaded rate and no conclusion is drawn.
- `iris-dev-iris` stays interoperability-enabled in BENCHMARK.
- The pyprod live test needs pyprod 0.2.0 on a throwaway IRIS container on an unregistered port,
  removed afterwards; `pyprod-proof` is pyprod's container and is not used.
- The lookalike's stub business operation answers within its timeout unless a fixed input asks it to
  sleep, so the timeout path is one of the fixed inputs.
