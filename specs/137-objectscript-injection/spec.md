# Feature Specification: No tool parameter runs as ObjectScript

**Feature Branch**: `feat/improve-cli` (no branch of its own, like 130 to 136)
**Created**: 2026-10-17
**Status**: Draft
**Input**: The `iris_global` finding of 2026-10-17 (fixed in `ee46c79`) and Tom's decision (Q9 of the 136
grilling) to sweep every tool before 136. The inventory is in `research.md`.

## Context

Many tools build ObjectScript, SQL or a document URL from their parameters and send it to IRIS. When a
parameter is spliced in unchecked, the caller's text becomes code. `iris_global` took `global_name`
that way: `X) Kill ^Y Set q=$Get(^X` closed the `$Get`, killed `^Y` and reopened it, so a read-only
`get` with `subtree=true` deleted a global with write tools off. A quote in `global_preview`'s name
did the same. Both now refuse a name that is not IRIS name syntax.

The caller is an AI agent. Text it reads (a field in a record, a file in the repository, a web page)
can carry instructions, so "the caller would not do that" is not a defence. The tiers, the
destructive gate, the data-policy gate and the system blocklist all assume that a tool does what its
name says. A splice breaks that assumption for every tool it touches.

TPRM-6601/6602 rated iris-agentic-dev "High" for use against environments holding personal and health
data. This spec is the work a reviewer would ask for after reading `ee46c79`.

## User Scenarios & Testing

### User Story 1 - A read-only tool cannot be made to write or run code (P1)

An operator runs iris-agentic-dev with write tools off. Whatever text an agent puts in any parameter
of a read-only tool, IRIS receives only the read the tool describes.

**Independent test**: for each site the inventory marks injectable, a live test sets a sentinel global,
calls the tool with a crafted parameter that would kill it, and asserts the tool refuses the parameter
and the sentinel is still there. Each test fails before its fix.

### User Story 2 - A gate cannot be stepped around by what a parameter contains (P1)

A connection's policy blocks a global, a category or a template action. No parameter text makes a tool
act on something the gate would have refused had it been named plainly.

**Independent test**: crafted inputs against each gate that inspects a parameter (system blocklist,
PHI names, destructive gate on `Kill`, data policy) are refused or evaluated on the real target.

### User Story 3 - A new tool cannot add a splice silently (P2)

A developer adds a tool that builds ObjectScript from a parameter. A guard test fails until the
parameter goes through a validator or an escaping helper, the way the test-target layout guard fails
on an unlisted file.

**Independent test**: a scratch site that splices a parameter with no helper makes the guard fail.

### Edge cases

- A parameter is legitimately free text inside a string literal (a description, a search term): it is
  escaped for that literal (doubled quotes), not refused.
- A parameter is a class, routine, production, item or table name: it is checked against IRIS name
  syntax for that kind of name and refused with a named error code otherwise.
- A name containing `%` or `.` that IRIS accepts must still pass (`%Library.String`, `Ens.Director`).
- Values read back from IRIS and sent again in a second call are treated as caller text.
- `iris_execute` and `iris_execute_method` exist to run code; they are out of scope except where a
  gate inspects their text and a splice can make the gate see something else.
- SQL: literals with doubled single quotes are safe; an identifier spliced into SQL is checked as an
  identifier.
- A refused parameter never reaches IRIS: the refusal happens before any network call.

## Requirements

### Functional Requirements

- **FR-001**: `research.md` lists every site where caller text reaches ObjectScript, SQL, a document URL
  or a command line, with its tool, tier, placement, current escaping and verdict.
- **FR-002**: Every site marked injectable is fixed by validation (names) or escaping (free text) at
  the point of use, through a small set of shared helpers, not one-off code per tool.
- **FR-003**: A refused parameter returns a specific error code (`INVALID_GLOBAL_NAME`,
  `INVALID_CLASS_NAME` and so on) with a message that says what the syntax is, in the style of
  `INVALID_GLOBAL_NAME`.
- **FR-004**: Each fix has a live test against `iris-dev-iris` that fails before the fix: a sentinel
  survives, or the gate refuses.
- **FR-005**: Valid names that IRIS accepts, including `%` packages and dotted names, pass every
  validator; unit tests list them.
- **FR-006**: A guard test finds ObjectScript-building sites that take a parameter without a helper.
- **FR-007**: `SECURITY.md` and `docs/production-profile.md` say what was found and fixed, plainly, in
  the release notes style the constitution asks for, once the fixes land.
- **FR-008**: No behaviour change for valid input: the existing unit, binary and live suites pass.

### Key Entities

- **Splice site**: a place in the source where caller text becomes part of code, SQL, a URL or a
  command, with its tool, tier, placement and verdict.
- **Validator / escaper**: the shared helpers a site must use, one per kind of name plus one for free
  text in a literal.

## Success Criteria

- **SC-001**: Every site in `research.md` has a verdict, and every injectable one has a fix and a live
  test that failed first.
- **SC-002**: With write tools off, no crafted parameter of any read-only tool changes data on IRIS in
  the live suite.
- **SC-003**: The guard test fails on a deliberately added unchecked splice and passes on the tree.
- **SC-004**: The full suite (`--include-ignored`, serial) passes after the fixes.

## Assumptions

- The inventory is a source review plus live crafted-input tests on `iris-dev-iris`; no fuzzing or
  external penetration test is part of this spec (`SECURITY.md` says none has been done).
- A fix that changes an error code for valid input is a regression and is not accepted.
- Disclosure: this repository is public. The fix commits say what they fix; Tom decides whether a
  GitHub security advisory goes with the next release. Nothing is published from here.
