# improve

The vocabulary of the improvement loop. It is about running a project's own evaluation over time and
deciding what to fix next; the project's domain words are in the project's own glossary.

## Language

### The experiment

**Task**:
One piece of work with a check that decides whether it was done: a prompt, the state it starts in, and
a check that is false before and true after a correct solution. Its id is stable.
_Avoid_: test case, scenario, benchmark item

**Arm**:
One way of running every task: the same tasks, the same check, a different setup. The loop compares two.
_Avoid_: condition, variant, group

**Baseline arm**:
The arm with nothing added. It says what the agent does without the treatment.
_Avoid_: control (when the arm has other things switched on), vanilla

**Treated arm**:
The baseline plus the one thing being tried. The difference between the arms is what the loop measures.
_Avoid_: experimental arm, test arm

**Holdout**:
The tasks nobody has tuned anything against. A result is only reported from them. A task moves to the
train side the moment someone changes the treatment while looking at it.
_Avoid_: test set, validation set

**Train side**:
Tasks the treatment may be fitted to. Their results are never published and never count as the result.
_Avoid_: dev set

**Full holdout**:
A run record that covers enough holdout tasks, in both arms, to report from. A spot check of a few tasks
is not one.
_Avoid_: complete run

### The work

**Worklist**:
The tasks that failed in the last full holdout, ranked: failed in both arms first, then made worse by
the treatment, then passing only when treated. Derived from the run record each time, never kept by hand.
_Avoid_: backlog, queue, todo list

**Sound** (of a task):
Its check is false before and true after its reference solution. A task that is not sound is the
problem, and the agent is not to be blamed for failing it.
_Avoid_: valid, correct (these describe answers, not tasks)

**Iteration**:
One pass through the worklist: pick an item, find the cause, change one thing, re-run, keep or revert.
It has an id, `IMP-NNNN`, that every record of the pass carries.
_Avoid_: experiment, sprint, round

**Adapter**:
`project.toml`. Every fact the engine needs about the project, and the only file a new project writes.
_Avoid_: config (it is the project's definition, not tuning), plugin

**Engine**:
The code that runs the loop. It knows nothing about the project, which is why it can move between them.
_Avoid_: framework, harness (the harness is the project's own thing that produces run records)

### The record

**Ledger**:
The append-only file of what the loop did and what it cost. A claim of improvement points at an entry in
it. Status is computed from run records and the ledger, never read from prose.
_Avoid_: log, history, journal

**Cap**:
A dollar limit on measured spend, enforced as the run goes. An estimate is not a cap: estimates have run
3 to 35 times low.
_Avoid_: budget (the budget is the amount; the cap is the stop)
