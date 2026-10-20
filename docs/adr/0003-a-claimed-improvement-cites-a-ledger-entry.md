# 0003: A claimed improvement cites a ledger entry

Date: 2026-10-12. Status: accepted for the verbs that exist; the commit-trailer check is not built.

## Context

Things the loop did could not be traced afterwards. The scheduled nightly failed 27 of its last 30
runs, and finding out why meant opening each run's log by hand. The 1.5.0 skill sweep cost $63 and the
AI Hub holdout $12.29 against a $3 cap, and there was no ledger to total those from. The
practice that addresses this is the one described in arno's notes on Iran Hutchinson's deep dive
(`arno/docs/research/2026-10-08-iran-deepdive-pitch-material.md`): artifacts carry lineage ids, the id
sits in each source header, a defect is traced by id back to its design, every finding goes into an
evidence ledger as its source is read, and a different agent verifies. Those notes are second-hand, say
that nothing in them has been discussed with Iran, and read only part of his documents. This ADR takes
the idea, not his scheme.

## Decisions

- **Every iteration has an id, `IMP-NNNN`,** assigned when the first ledger entry for it is written. All
  later records of that pass carry it.
- **The ledger is append-only,** one JSON object per line in `.improve/ledger.jsonl`, with `ts`, the
  `id`, an `event` and the fields that event needs. Events are `claim` (who took the item), `run`
  (the run record it produced, its measured cost), `verdict` (kept or reverted, with the before and after
  counts and the run ids they came from) and `change` (the commit).
- **No identifier, no claim.** A statement that the loop improved something, in a commit, a release note
  or a report, names an `IMP` id, and the id's `verdict` entry names the runs behind it.
- **Results are derived, never stored.** `status` computes the scoreboard and the worklist from run
  records every time. The ledger records events and spend; it does not hold a scoreboard that could
  disagree with the records.
- **One holder per worklist item.** A `claim` entry names the agent or person taking it, and `next`
  refuses to hand out an item with an open claim by someone else. The agent bus's `claim_task` is the
  same idea across sessions.
- **A different run verifies.** A change is kept on the strength of a re-run of the affected tasks, not
  on the author's reading of a transcript. The author does not write the `verdict`; the re-run's numbers
  do.

## Considered options

- **Notes in the pull request or the commit message only.** They are read once and cannot be queried, so
  "what did we spend on this" has no answer.
- **Issues in the tracker as the record.** Public, one per item, and the loop's chatter would be noise
  there; it also makes the loop depend on network access to read its own history.
- **Store the scoreboard in a file the loop updates.** Fast to read, and it will eventually disagree with
  the run records.
- **Lineage ids on every file as Iran's scheme has them.** More than this loop needs. One id per
  iteration is enough to trace a change to the runs behind it.

## Consequences

- `try` and `week` must write ledger entries before they report a result, which is also what makes
  `status` able to show spend. Until they exist `status` says spend is "not tracked yet".
- A check that rejects a commit message claiming an improvement without an `Improve: IMP-NNNN` trailer is
  the natural enforcement. It is not built, so today this rule is followed by habit.
- Holds while iterations are small enough to have one cause. A change that moves ten tasks at once would
  need a verdict per task, and the `verdict` shape would have to grow.
