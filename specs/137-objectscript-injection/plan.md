# Implementation Plan: No tool parameter runs as ObjectScript

**Branch**: `feat/improve-cli` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)
**Input**: `spec.md`, and the inventory in `research.md` (42 sites need a fix, 6 unsure, 38 safe).

## Summary

Caller text reaches generated ObjectScript, SQL, Atelier URLs and one remote shell command without
escaping at about 40 sites. The fix is mechanical once the helpers exist: free text inside an
ObjectScript literal goes through `os_str_expr` (already in `src/objectscript.rs`, already correct),
SQL values become `?` parameters, names go through one validator per kind of name, URL segments are
encoded, and the shell command quotes or refuses. Three gates that never ran on three tools are
wired in. A detector in `scripts/gates/antipatterns.py` records the remaining quoted splices in its
baseline and fails on any new one, so the list can only shrink.

## Technical Context

**Language/Version**: Rust 2021 (workspace), Python 3.11 for the gate detector
**Primary Dependencies**: existing only (`regex`, `urlencoding`, `serde_json`); no new crate
**Storage**: N/A
**Testing**: `cargo test --features testing` (`unit` for validators, `integration` for live sentinel
tests, serial); `scripts/gates/test_antipatterns.py` for the detector
**Target Platform**: the `iris-agentic-dev` binary on macOS, Linux, Windows
**Project Type**: single workspace, two crates
**Performance Goals**: validation is a regex per parameter; no measurable cost
**Constraints**: no error-code or output change for valid input (FR-008); a refusal happens before any
network call; valid IRIS names (`%Library.String`, `Ens.Director`, `IRIS.Temp.X`) must pass
**Scale/Scope**: about 40 sites in 14 files; 3 gate wirings; 1 detector

## Constitution Check

| Principle                     | Status | Notes                                                                                                                        |
| ----------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------- |
| I. Zero-Install Binary        | PASS   | No new install step                                                                                                          |
| II. ObjectScript Sanity       | PASS   | Every changed ObjectScript builder is exercised by a live test on 2026.2                                                     |
| III. HTTP-First Execution     | PASS   | No new docker-only path; the docker stdin paths get the same escaping                                                        |
| IV. Test-First                | PASS   | Each site: a live sentinel test that fails first; validators: unit tests first                                               |
| V. Output Shape Parity        | PASS   | New error codes follow `INVALID_GLOBAL_NAME`; valid-input output unchanged                                                   |
| VI. Environment Guard         | PASS   | The point of the spec: read-only tools stop being able to write                                                              |
| VII. Dependency Minimalism    | PASS   | No new crate                                                                                                                 |
| VIII. 90% Coverage Gate       | PASS   | Coverage check in the polish phase; the change adds tests, not untested code                                                 |
| IX. Tool Lift                 | N/A    | No new tool and no description change                                                                                        |
| X. ObjectScript Coverage      | N/A    | No ObjectScript classes ship                                                                                                 |
| XI. No Vacuous Tests          | PASS   | Sentinel tests assert the sentinel unconditionally; validator tests assert non-empty name lists                              |
| XIII. Single-Source Detection | PASS   | One helper per kind of escaping; the detector finds sites that bypass them                                                   |
| Bug Class Registry            | ACTION | New class "caller text spliced into code" with detector `objectscript-splice`; amendment via `/speckit.constitution` (MINOR) |
| Error Code Registry           | ACTION | New codes listed in `data-model.md`                                                                                          |

No FAIL gate.

## Design

### Helpers (`crates/iris-agentic-dev-core/src/objectscript.rs`)

- `os_str_expr(s)`: existing. Emits a complete ObjectScript string expression, quotes included, with
  `"` doubled and control characters as `$C(...)`. Every free-text site uses it and drops its own
  surrounding quotes.
- `validate_class_name`, `validate_routine_name` (routine or document name with its extension),
  `validate_namespace`, `validate_method_name`, `validate_sql_identifier`, `validate_timestamp`
  (journal `start`/`end`): each `Result<(), Value>` with the error codes in `data-model.md`, in the
  shape of `validate_global_name`, which moves here from `tools/global.rs` (re-exported there).
- SQL values: `?` parameters through `iris.query(sql, params, …)`, as `query_audit_log` does. A
  helper `sql_str_literal` (doubled single quotes) only where a parameter cannot be bound.
- `resolve_namespace` (mod.rs) validates once, so every tool that takes `namespace` is covered.

### Gates

- `global_preview` and `global_kill` call `dispatch_gate`, and gates [3] (system blocklist) and [4]
  (PHI names) read `global` as well as `global_name`/`globalName`.
- The standalone `journal_search` calls `dispatch_gate`, so bulk-PHI block [2] applies to it as it
  does to `iris_admin action=journal_search`.
- `contains_global_kill` covers a multi-argument `Kill` whose protected global is not the first
  argument.

### Shell

- The ssh remote command (connection.rs:897) refuses a namespace or container outside its validator
  and single-quotes both for the remote shell.

### Detector `objectscript-splice` (`scripts/gates/antipatterns.py`)

Flags, in `crates/*/src/**/*.rs`: a `format!` placeholder sitting directly inside double quotes in an
ObjectScript string (`"{x}"` in a raw string, `\"{x}\"` in a normal one), a placeholder inside single
quotes in a string that contains SQL keywords (`'{x}'`), and `.replace('"', "\\\"")`, a backslash
escape ObjectScript does not have. The baseline starts with today's findings; each fix deletes its
line, and the gate fails on a stale line, so the baseline shrinks to zero. Once it is zero the
detector joins the never-baselined list. Limit, written in the detector: a bare `{x}` splice is not
flagged, because code builders splice generated fragments that way; the inventory covers those.

### Order (spec's ranking)

1. Helpers and validators with unit tests; the detector with its baseline.
2. Group A: read-only tools that can run code or free SQL (12 entries).
3. Group B: gates, the shell command, write-tier and destructive-tier splices.
4. Group C: URL encoding.
5. The 6 UNSURE: a live test decides each; fix or record as safe with the evidence.
6. Docs: `SECURITY.md`, `docs/production-profile.md`, constitution amendment.

## Project Structure

```text
specs/137-objectscript-injection/
├── spec.md, research.md, plan.md, data-model.md, quickstart.md
├── contracts/error-codes.md
└── tasks.md

crates/iris-agentic-dev-core/src/objectscript.rs           # helpers and validators
crates/iris-agentic-dev-core/src/tools/*.rs                # the sites
crates/iris-agentic-dev-core/src/iris/connection.rs        # ssh command
crates/iris-agentic-dev-core/src/tools/write_gate.rs       # multi-argument Kill
crates/iris-agentic-dev-core/tests/unit/test_os_validators_137.rs
crates/iris-agentic-dev-core/tests/integration/test_injection_137_live.rs
scripts/gates/antipatterns.py, antipatterns-baseline.txt, test_antipatterns.py
```

## Complexity Tracking

None. One helper module, one detector, mechanical edits at the sites.
