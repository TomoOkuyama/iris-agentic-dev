# Tasks: 137 No tool parameter runs as ObjectScript

Test first in every phase: the test task comes before the code task and must fail before it.
Live tests: `iris-dev-iris`, serial, write tools off. Paths are under
`crates/iris-agentic-dev-core/` unless they start with `scripts/` or `docs/`.

## Phase 1: Helpers and the detector

- [x] T001 Unit tests `tests/unit/test_os_validators_137.rs` (and its `mod` line): each validator in
      `data-model.md` accepts the listed IRIS names and refuses the crafted ones; `os_str_expr`
      round-trips a quote, `$C(10)` and an empty string
- [x] T002 Validators in `src/objectscript.rs`; `validate_global_name` moves there, re-exported from
      `tools/global.rs`
- [x] T003 Detector test in `scripts/gates/test_antipatterns.py`: a scratch file with `"{x}"` in an
      ObjectScript raw string, `'{x}'` in a SQL string and `.replace('"', "\\\"")` gives three findings;
      the same placeholders unquoted give none
- [x] T004 Detector `objectscript-splice` in `scripts/gates/antipatterns.py`; baseline written with
      today's findings, the commit message says why
- [x] T005 Live test file `tests/integration/test_injection_137_live.rs` (and its `mod` line) with the
      sentinel helpers: set, call, assert refusal code, assert sentinel

## Phase 2: Group A, read-only tools (research.md A1 to A12)

For each entry: a live sentinel test (fails first), then the fix with the helper, then its baseline
lines removed.

- [x] T010 A1 `iris_database_stats` `db`: path in `os_str_expr`
- [x] T011 A2 `journal_search` `start`/`end`: `validate_timestamp`, then `os_str_expr`
- [x] T012 A3 `iris_interop_query` `body_where`: refused (`INVALID_PARAMS`) unless it passes the
      read-only SQL check `iris_query` uses; decide by reading that check, record the decision
- [x] T013 A4 `debug_map_int_to_cls` `routine`, `debug_source_map` `cls_name`
- [x] T014 A5 `iris_debug` `error_string`, `class_name`
- [x] T015 A6 `iris_doc` mode=compiled `name`
- [x] T016 A7 `iris_coverage` report `classes[]`, `package`, including the docker stdin path
- [x] T017 A8 `stream_inspect` `oid`, `hl7_schema_inspect` `schema`/`segment`
- [x] T018 A9 `iris_table_info` `table`, `resolve_dynamic_dispatch` `method_name`/`prefix`
- [x] T019 A10 `skill` describe/search, `kb` recall, `skill_describe` docker stdin
- [x] T020 A11 `mermaid_class`, `mermaid_production`, `resolve_storage`: `?` parameters
- [x] T021 A12 `iris_admin` journal_search `time_range`
- [x] T022 `resolve_namespace` validates the namespace; one live test with a crafted namespace on a
      read-only tool

## Phase 3: Group B, gates and the shell

- [x] T030 B5 `global_preview` and `global_kill` call `dispatch_gate`; gates [3] and [4] read
      `global`; live test: a blocklisted and a PHI-named global are refused by both
- [x] T031 B5 standalone `journal_search` calls `dispatch_gate`; live test: refused under
      `dataPolicy=block`
- [x] T032 B4 `contains_global_kill` multi-argument `Kill`; unit tests first
- [x] T033 B1 ssh remote command: validate and single-quote namespace and container; unit test on the
      built command line
- [x] T034 B2 write-tier splices: `iris_production` start, `iris_admin` mirror_add_async, `iris_test`,
      `iris_compile` docker, `iris_execute_method` class/method, `skill` propose,
      `skill_community` install, `kb` index; one live test each where a live call is possible, unit
      test on the built code otherwise
- [x] T035 B3 destructive-tier splices: `iris_namespace_create`, `skill` forget / `skill_forget`

## Phase 4: Group C and the unsure

- [x] T040 C: encode `iris_macro` `includes[]`, `iris_search` `category`, `compare_*` namespace; unit
      tests on the built URL
- [x] T041 The 6 UNSURE entries: a live test decides each; fix, or record SAFE in `research.md` with
      the test that shows it

## Phase 5: Close

- [x] T050 Baseline for `objectscript-splice` is empty; the detector joins the never-baselined list
- [x] T051 Full suite `--include-ignored --test-threads=1`; unit, binary, live all pass; clippy and fmt
- [ ] T052 Coverage check (constitution VIII) on the touched files — not run in this session; the 90% gate needs a full `--include-ignored` coverage run
- [x] T053 Constitution amendment via `/speckit.constitution`: Bug Class Registry row "caller text
      spliced into code", detector `objectscript-splice` (MINOR)
- [x] T054 `SECURITY.md` and `docs/production-profile.md`: what was found and fixed, plainly
- [x] T055 `research.md` updated: every row has its fix and its test, or its SAFE evidence
