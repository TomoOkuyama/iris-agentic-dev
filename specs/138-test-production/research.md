# 138 research: does iad capture `%UnitTest.TestProduction`?

Question (Tom, 2026-10-20): does iad properly capture the Interoperability extension to `%UnitTest`,
`%UnitTest.TestProduction`, as taught by the Testing Productions tutorial (book key TTEP)?

Short answer: partly. `iris_test` can launch a TestProduction subclass, but no skill teaches an agent
to write one, one skill gives a method that does not exist, the generators always produce a plain
`%UnitTest.TestCase`, and nothing tests the path against live IRIS. Details and a ranked gap list
follow.

Sources read (2026-10-20):

- Every TTEP page, fetched with a browser User-Agent from `irislatest` DocBook. The page body is in
  the served HTML inside `<article>`, so the `intersystems-docs` skill's claim that DocBook bodies are
  only loaded client-side does not hold for these pages. Algolia (`group:IRIS2026.2`) indexes 16 of
  the 18 pages; it misses `TTEP` (book index) and `TTEP_ExampleOperation`. Both were read from
  DocBook directly.
- The Documatic page for `%UnitTest.TestProduction`
  (<https://docs.intersystems.com/irislatest/csp/documatic/%25CSP.Documatic.cls?LIBRARY=%25SYS&CLASSNAME=%25UnitTest.TestProduction>),
  HTTP 200; its text matches the class source below.
- Live container `iris-dev-iris` (IRIS for UNIX 2026.2.0L Build 208U), read only: the source of
  `%UnitTest.TestProduction`, `%UnitTest.Manager`, `%UnitTest.TestCase`, `EnsLib.Testing.Service`,
  `Ens.Director` through `GET /api/atelier/v1/USER/doc/...`, and `%Dictionary.CompiledMethod` /
  `CompiledParameter` / `CompiledClass` / `CompiledProperty` queries. Nothing was created or run.
  Cited as `TestProduction.cls:N` (line in the served source).
- iad at `6fc3321` (branch `feat/improve-cli`).

## 1. The tutorial, page by page

The DocBook URLs below use the prefix
`https://docs.intersystems.com/irislatest/csp/docbook/DocBook.UI.Page.cls?KEY=`. The table gives
the KEY only.

| #   | KEY                                    | Title                              |
| --- | -------------------------------------- | ---------------------------------- |
| 0   | `TTEP`                                 | Testing Productions (book index)   |
| 1   | `TTEP_intro`                           | Testing Productions Tutorial       |
| 2   | `TTEP_TestProd`                        | Testing Productions                |
| 3   | `TTEP_TestProd_Overview`               | TestControl                        |
| 4   | `TTEP_TestProd_Callbacks`              | Callback Methods                   |
| 5   | `TTEP_TestProd_HelperMethods`          | Auxiliary Methods                  |
| 6   | `TTEP_TestProd_ParamsAndProps`         | Parameters and Properties          |
| 7   | `TTEP_TestProd_CreationSummary`        | Creating a Test - Summary          |
| 8   | `TTEP_TestProd_Execute`                | Executing a Test                   |
| 9   | `TTEP_TestProd_ExampleOverview`        | Example Overview                   |
| 10  | `TTEP_TestProd_ExampleProd`            | Example: Example Production        |
| 11  | `TTEP_TestProd_Start`                  | Example: Production Test           |
| 12  | `TTEP_TestProd_OnAfterProductionStart` | Example: OnAfterProductionStart    |
| 13  | `TTEP_TestProd_CheckResults`           | Example: CheckResults              |
| 14  | `TTEP_TestProd_CheckError`             | Example: CheckErrors               |
| 15  | `TTEP_TestProd_ExecuteOptions`         | Example: Executing the Test        |
| 16  | `TTEP_TestProd_Recap`                  | Recap                              |
| 17  | `TTEP_ExampleOperation`                | Creating Tutorial.ExampleOperation |

All 18 pages were fetched. Page 15's terminal output is an image
(`images/ttep_testprod_run_20181.png`), which I read.

### Facts, with citations

Each fact is tagged `T-n` for the comparison in section 3.

#### Class and structure

- **T-1. Extend `%UnitTest.TestProduction`.** "Create a test class. The class must extend
  %UnitTest.TestProduction." (`TTEP_TestProd_CreationSummary`) The live class is
  `Class %UnitTest.TestProduction Extends %UnitTest.TestCase [ System = 3 ]` (`TestProduction.cls:75`).
- **T-2. No `TestX` methods.** "When you create production tests you do not implement any TestX
  methods. In this way creating production tests with %UnitTest.TestProduction differs significantly
  from creating tests using %UnitTest.TestCase." (`TTEP_TestProd_Overview`) The one test method is
  the inherited `TestControl` (`TestProduction.cls:909`, `[ Internal ]`, so Documatic hides it).
- **T-3. `TestControl` drives the run.** "When you launch a test, the %UnitTest.TestProduction
  TestControl method executes. This method starts and stops the production being tested and also
  invokes a series of callback methods." (`TTEP_TestProd_Overview`)
- **T-4. `PRODUCTION` is required.** "This is required. The value is the name of the production to
  be tested." (`TTEP_TestProd_ParamsAndProps`) The compiler enforces it:
  `If %parameter("PRODUCTION")="" Quit $$$ERROR($$$GeneralError, "Parameter PRODUCTION must be specified")`
  (`TestProduction.cls:788`).
- **T-5. Interoperability namespace only.** The tutorial says to "Create a new
  interoperability-enabled namespace" (`TTEP_TestProd_ExampleOverview`). The class refuses to
  compile anywhere else: "This class is only for use in Ensemble and HealthShare systems"
  (`TestProduction.cls:779`). On `iris-dev-iris`, `USER` and `BENCHMARK` are interop-enabled;
  `BIZ` and `IADSBI` are not (`^%SYS("Ensemble","InstalledNamespace",ns)`).

#### Callbacks (`TTEP_TestProd_Callbacks`; signatures from `%Dictionary.CompiledMethod`)

- **T-6. `OnBeforeProductionStart() As %Status`.** "Peform tasks immediately before the production
  starts, for example: Adjusting Production Settings, Creating Directories, Copying Files, Creating
  Credentials". Class doc: "If an error status is returned, the test will be aborted and failed."
  (`TestProduction.cls:155`)
- **T-7. `OnAfterProductionStart() As %Status`.** "from this method you can use SendRequest to send
  request messages to production components."
- **T-8. `CheckResults(ByRef Log As %String, New As %String) As %Status`.** "Verify the results of
  running the production. For example, from this method you can examine the contents of the Event
  Log or query the database."
- **T-9. `CheckErrors() As %Status`.** "This method is invoked only if IGNOREPRODUCTIONERRORS = 1."
- **T-10. `OnBeforeProductionStop()` and `OnAfterProductionStop()`**, both `As %Status`.
- **T-11. `OnBeforeOneTest` / `OnAfterOneTest` still apply.** "You can also place initialization and
  clean-up code in OnBeforeOneTest and OnAfterOneTest as in the case of unit tests".
- **T-12. Actual order (not in the tutorial).** The tutorial's table lists CheckErrors before the stop
  callbacks. `TestControl` (`TestProduction.cls:909-945`) runs:
  1. `OnBeforeProductionStart`. An error status quits the test; the production is never started.
  2. `StartProduction`.
  3. `OnAfterProductionStart`. An error status in either step jumps to `Stop`.
  4. A wait of `MINRUN` seconds.
  5. `GetEventLog("infouser", "", BaseLogId, .Log, .New)`, then `CheckResults(.Log, New)`.
  6. `OnBeforeProductionStop`.
  7. `Stop:` `StopProduction`, then `OnAfterProductionStop`.
  8. With `IGNOREPRODUCTIONERRORS` = 1, `CheckErrors()`. Otherwise
     `$$$AssertEquals($D(Err), 0, "Verifying no production errors occurred")` over every Error-type
     Event Log entry since `BaseLogId`.

  So CheckErrors runs after the production has stopped. The page 15 screenshot shows the same order.

- **T-13. CheckErrors' return value is ignored.** `Do ..CheckErrors()` (`TestProduction.cls:934`).
  Only assertions inside it count. The tutorial's `if 's1||'s2 set tSC=..Error(...)` in CheckErrors
  (`TTEP_TestProd_CheckError`) has no effect on the result. CheckResults is wrapped in
  `$$$AssertStatusOK`, so an error status returned from it does fail (`TestProduction.cls:926`).

#### Parameters (`TTEP_TestProd_ParamsAndProps`; defaults confirmed in `%Dictionary.CompiledParameter`)

- **T-14. `IGNOREPRODUCTIONERRORS` = 0.** "Set the value to 1 when you expect production errors
  during the test. If the value is 0 then an error causes the test to fail."
- **T-15. `MAXWAIT` = 10.** "The maximum number of seconds to wait for the production to completely
  start before proceeding". The class doc says "start or stop" (`TestProduction.cls:81`). It is not
  only a maximum: `StartProduction` always runs `Hang ..#MAXWAIT-(($ZH-t0-.5)\1)` after
  `Ens.Director.StartProduction` (`TestProduction.cls:858`), so every run pays roughly MAXWAIT
  seconds at start-up. Raising MAXWAIT makes every run longer.
- **T-16. `MINRUN` = 10.** "The minimum number of seconds to allow the production to run before
  invoking callback methods such as GetEventLog and CheckResults and then stopping the production."
  The wait loop is at `TestProduction.cls:915-922`.
- **T-17. Properties.** The tutorial gives a partial list: `BaseLogId` ("the first Event Log ID for
  entries generated by the production during the test"), `LastLogId`, `InstanceName`,
  `MachineName`, `DSNToUser`. The class adds `MainDir`, `HL7InputDir`, `HL7OutputDir`,
  `HL7WorkDir`, `HL7ArchiveDir`, `DSNToSamples` (`TestProduction.cls:98-128`).

#### Auxiliary methods (`TTEP_TestProd_HelperMethods`; signatures from the live dictionary)

- **T-18. `SendRequest`.** `ClassMethod SendRequest(Name As %String = "", Req As %RegisteredObject, ByRef Resp As %RegisteredObject, GetReply As %Boolean = 0, Time As %Integer = 30) As %Status`.
  The tutorial says: "Use this method to call the Testing Service to send a request message to a
  component. Note that testing must be enabled for the production." `GetReply=1` waits up to `Time`
  seconds, polling `Ens.MessageHeader` once a second (`TestProduction.cls:341-349`). It calls
  `EnsLib.Testing.Service.SendTestRequest`, which calls
  `Ens.Director.CreateBusinessService("EnsLib.Testing.Service")`. `Ens.Director` only adds
  `EnsLib.Testing.Service` and `EnsLib.Testing.Process` when `TestingEnabled` is true on the
  production or in System Default Settings (`Ens.Director` source, lines 870-910).
  `Ens.Config.Production.TestingEnabled` defaults to `""`. The tutorial's example never says how to
  turn it on. The tutorial calls `..SendRequest("Tutorial.ExampleOperation", request, .response, 1, 40)`
  (`TTEP_TestProd_OnAfterProductionStart`).
- **T-19. `GetEventLog`.** `Method GetEventLog(type As %String = "all", name As %String = "", baseId As %Integer, ByRef v As %String, Output New As %Integer) As %Status`.
  Types: `all info error trace warning alert assert infouser startstop other`
  (`TestProduction.cls:387`). `infouser` drops `Ens.Director` Start/Stop/UpdateProduction and
  `Ens.Job:Start` entries (`TestProduction.cls:473-484`). If `baseId` is `""`, it reads from
  `LastLogId`, not `BaseLogId` (`TestProduction.cls:456-458`). The tutorial's CheckErrors passes
  `""`, so it only sees errors after the last Info entry CheckResults read. It gets 3 because of
  where the errors happen to fall. The class's own default CheckErrors passes `..BaseLogId`
  (`TestProduction.cls:204`). `v` is appended with `$I(v)` and never killed, so reusing a variable
  accumulates entries.
- **T-20. Log array shape.** "The Log array contains a node corresponding to each piece of Event Log
  information including: Text, Type, TimeLogged, SessionId, SourceMethod, and ConfigName."
  (`TTEP_TestProd_CheckResults`) The full set is `ID TimeLogged Type Job SessionId ConfigName SourceClass SourceMethod Text Stack`
  (`TestProduction.cls:491`).
- **T-21. Other helpers.** `CopyFile`, `CompareFiles`, `CreateMainDirTree` (default
  `TestAutoNNN` "at the same level as the installation directory"), `CreateCredentials`
  (`TTEP_TestProd_HelperMethods`). The class reference also has `GetSetting`, `ChangeSetting`
  (with `saveToProduction`), `Error`, `LogErrors`, `SelectToString`, `CleanUpDirectory`,
  `ListSettings`, `Export`, `Run`, `Debug` (`TestProduction.cls:35-74`). There is no
  `GetEventLogErrors`, `GetMessageHeaders` or `CreateMainProduction`. `CopyFile` and `CompareFiles`
  default one directory to `..Manager.CurrentDir`, which comes from `^UnitTestRoot`.

#### Running (`TTEP_TestProd_Execute`, `TTEP_TestProd_ExecuteOptions`)

- **T-22. `Run()` and `Debug()`.** "TestProduction provides a pair of convenience methods: Run and
  Debug." Run "Runs the test currently loaded in InterSystems IRIS. It does not load any code from
  ^UnitTestRoot. It does not delete any code". In the source, Run is
  `##class(%UnitTest.Manager).DebugRunTestCase("", class, "/debug=0/recursive=0")`
  (`TestProduction.cls:525`), and Debug passes `/debug=1` (`TestProduction.cls:536`).
  `DebugRunTestCase` becomes
  `RunTest(":"_testcase_":", "/norecursive"_qspec_"/noload/run/nodelete")` (Manager source, line
  433). So `Run()` is `RunTest` on one class with `/noload/nodelete`. Nothing is specific to
  productions.
- **T-23. `%UnitTest.Manager` works as well.** "In addition, %UnitTest.TestManager provides several
  methods, including RunTest and DebugRunTestCase." Tutorial error: `%UnitTest.TestManager` does not
  exist (the live dictionary has `%UnitTest.TSQL`, `TestCacheScript`, `TestCase`, `TestProduction`,
  `TestScript`, `TestSqlScript`). The class is `%UnitTest.Manager`, which the same page names
  correctly two sentences later.
- **T-24. `^UnitTestRoot`.** "All of these methods require that you assign the global ^UnitTestRoot
  to either a valid path on the system where you are executing the test or the empty string". "The
  delimiters around the path name must be double-quotes". The example uses
  `Set ^UnitTestRoot=""`, then `Do ##class(Tutorial.ProductionTest).Run()`. In the 2026.2 source,
  `Manager.Root()` falls back to `$$$envSourceDir_"internal/testing/unit_tests/"` when the global is
  undefined. Whether an undefined global breaks `Run()` on 2026.2 is unsettled (see section 5).
- **T-25. Reporting.** "Notice that the last line is a URL. Use this URL to view an HTML report on
  the test." The screenshot shows a `%UnitTest.Portal.Indices.cls?Index=4&$NAMESPACE=TUTORIAL` URL,
  `TestControl passed`, `Tutorial.ProductionTest passed`, `All PASSED`, and
  `LogMessage:Duration of execution: 22.246897 sec.` with the default MAXWAIT and MINRUN. Each
  framework step is printed as an assertion, for example
  `AssertStatusOK:Invoking Ens.Director::StopProduction (passed)`.

#### Example production (`TTEP_TestProd_ExampleProd`, `TTEP_ExampleOperation`, `TTEP_TestProd_Start`)

- **T-26. The example.** `Tutorial.ExampleOperation Extends Ens.BusinessOperation` with
  `INVOCATION = "Queue"` and a `MessageMap` from `Ens.StringRequest` to `Test`. It returns `"OK"` /
  `"ERROR"`, sets `$$$ERROR($$$GeneralError, "Test error case")` on an empty input, and logs
  `$$$LOGINFO(pResponse.StringValue)`. The test class is
  `Class Tutorial.ProductionTest Extends %UnitTest.TestProduction { Parameter PRODUCTION = "Tutorial.ExampleProduction"; Parameter IGNOREPRODUCTIONERRORS = 1; }`.
  The operation is added "do not assign it any name", so its config name equals the class name.
- **T-27. Tutorial code defect.** The `TTEP_ExampleOperation` listing closes the class with `}`
  before `XData MessageMap`, so the listing does not compile as printed.
- **T-28. Three errors per failing request.** "there should be three new errors in the Event Log:
  one generated by each of Tutorial.ExampleOperation, the testing process, and the testing service."
  (`TTEP_TestProd_CheckError`)

#### Pitfalls the class source shows and the tutorial does not mention

- **T-29. It stops whatever production is running.** If the namespace's production is not stopped,
  `StartProduction` stops it. If that fails, it force-stops (`StopProduction(,1)`), then runs
  `CleanProduction(1)` (`TestProduction.cls:828-844`). It never restarts the old one. Running a
  TestProduction in a namespace where a developer's production is up takes that production down.
- **T-30. Minimum duration.** About `MAXWAIT + MINRUN` plus 3 to 5 seconds (22 s at defaults per
  the screenshot), plus up to `Time` seconds per `SendRequest(...,1,Time)` and up to `MAXWAIT` for
  each `WaitForState` that has to wait. The cleanup path after a running production adds about
  2 × MAXWAIT more.
- **T-31. Production health check.** After start, `$$$AssertNotTrue(##class(Ens.Director).ProductionNeedsUpdate(.tReason), ...)`
  fails the start when the production needs an update, and logs each reason
  (`TestProduction.cls:861-877`).

## 2. What iad has today

### `iris_test` tool

- Parameter `test_type`: `auto`, `testcase`, `testproduction`
  (`crates/iris-agentic-dev-core/src/tools/mod.rs:877-882`). Default `timeout` is 60 s
  (`mod.rs:885-887`).
- Tool description: "'auto' (default) auto-detects %UnitTest.TestProduction subclasses and calls
  .Run()" (`mod.rs:4085`). It does not mention that a production is started and stopped, that a
  running production is stopped, `TestingEnabled`, MAXWAIT/MINRUN, or the timeout a production run
  needs.
- Detection (`mod.rs:4145-4169`). The superclass is probed only when the pattern is a single class
  name with no `/`, `\` or `*`. The probe (`build_superclass_probe`, `mod.rs:1360-1366`) is
  `%Dictionary.ClassDefinition.%OpenId(cls).Super` with
  `$find(oref.Super,"%UnitTest.TestProduction")`, which checks direct superclasses only. A probe
  error or a 10 s probe timeout reads as "not a TestProduction".
- Run code (`build_test_run_code`, `mod.rs:1324-1356`). TestProduction:
  `do ##class(<pattern>).Run()` (`mod.rs:1341`). Otherwise
  `RunTest("<pattern>","/verbose=1/nodelete/noload","<token>")` for class patterns. A directory
  pattern sets `^UnitTestRoot="/tmp/httest/"` (`mod.rs:1348-1352`), overwriting the user's global.
- Execution. Docker exec when `IRIS_CONTAINER` is set, otherwise `execute_via_generator`
  (`mod.rs:4217-4275`). That path PUTs a scratch class `IrisDevTmp.IrisDevRun<id>`, compiles it and
  runs `SELECT IrisDevTmp.IrisDevRun<id>_Execute()` over Atelier `/action/query`
  (`crates/iris-agentic-dev-core/src/iris/connection.rs:600-721`). The whole TestProduction run,
  including `Ens.Director.StartProduction`, happens inside one HTTP SQL request. On timeout, iad
  returns `TIMEOUT` (`mod.rs:4257-4264`).
- Result parsing (`mod.rs:4299-4374`). Only lines whose method name starts with `Test` count
  (`mod.rs:4343`). For a TestProduction that is the single `TestControl` line, so `total` is 1. The
  failure message comes only from a `--` separator (`mod.rs:4350-4355`). The 2026.2
  `%UnitTest.Manager` source has no `--` string; failed assertions print as
  `<action>:<desc> (failed)  <<==== **FAILED** suite:case:method` (Manager source, lines 1738 and
  1767). So `failure_message` is null, and the failing assertions (which callback, which expected
  value) are only in `raw_output` behind `log_id` / `iris_get_log` (`mod.rs:4446`). The report URL
  and the `Duration of execution` line are not surfaced.
- Tests. String-shape unit tests only:
  `crates/iris-agentic-dev-core/tests/unit/test_tools_mod_unit.rs:2383-2440`
  (`build_test_run_code_testproduction_class_pattern`, `..._false_for_directory_path`,
  `build_superclass_probe_*`) and the 137 injection test (`tests/unit/test_os_validators_137.rs:387`).
  No live or binary test runs a TestProduction subclass. The project's own three-layer policy
  (CLAUDE.md, Test Coverage Policy) requires a live layer here.
- History. Issue #99 ("%UnitTest.TestProduction suites can't run ... reports NO_TESTS_FOUND"), fixed
  in v1.2.0 (`docs/release-notes/v1.2.0.md:104-107`). No live test was added with the fix.
- `docs/tools.md:553-569`: the `iris_test` table has no `test_type` (or `server`) row, does not
  mention TestProduction, and gives the `namespace` default as `"USER"`. The code uses the
  connection namespace (`mod.rs:4099`).

### Skills

`grep -rni testproduction skills/` returns nothing. No skill mentions `%UnitTest.TestProduction`,
`SendRequest` (TestProduction's), `TestingEnabled`, `EnsLib.Testing.Service`, MAXWAIT, MINRUN or
`IGNOREPRODUCTIONERRORS`.

- `skills/skills/objectscript-unit-test/SKILL.md:4,15`: "Generates %UnitTest.TestCase subclasses".
  Line 68: "Only methods whose names start with `Test` run", which is the opposite of T-2 for
  productions. It has no branch for testing a production or its hosts.
- `skills/skills/objectscript-tdd/SKILL.md`: generic compile-test loop; no interop content.
- `skills/skills/iris-objectscript-eval/SKILL.md:147-168`: `^UnitTestRoot` and `RunTest` via docker
  exec, TestCase only.
- `skills/skills/ensemble-production/SKILL.md:548-582`, "Testing without the Management Portal",
  is the only testing guidance for productions. It teaches `Ens.Director.CreateBusinessService` +
  `ProcessInput` through `iris_execute`. It also teaches
  `##class(Ens.Director).SendRequestSync("MyProcessConfigName", req, .resp, 30)` (line 577).
  `Ens.Director` has no `SendRequestSync` or `SendRequest*` method (live
  `%Dictionary.CompiledMethod` query returns nothing; the source has none), so that call fails with
  `<METHOD DOES NOT EXIST>`. The real equivalents are `%UnitTest.TestProduction.SendRequest` or
  `EnsLib.Testing.Service.SendTestRequest`, and both need `TestingEnabled`. Its safety rules
  ("Prefer a graceful stop", line 465) say nothing about a TestProduction force-stopping a running
  production (T-29).

### Generators

- `iris_generate_test`: "Generate a %UnitTest.TestCase for an existing ObjectScript class"
  (`mod.rs:6017`). The system prompt is "Extend %UnitTest.TestCase / Test methods MUST start with
  "Test"" (`crates/iris-agentic-dev-core/src/generate.rs:330-336`).
- `iris_generate gen_type=test`: "Write an InterSystems IRIS %UnitTest.TestCase subclass ... prefix
  test methods with 'Test' ... include ##class({}).%New() in setup"
  (`crates/iris-agentic-dev-core/src/tools/info.rs:808`).

Neither checks whether the target is an `Ens.Production`, `Ens.BusinessOperation`,
`Ens.BusinessProcess` or `Ens.BusinessService`. For a business host they tell the agent to `%New()`
it and call its methods outside a production.

### Eval tasks

No task under `tests/e2e/tasks` mentions `TestProduction`, `TestingEnabled` or production tests run
through `%UnitTest`. The nearest is `tests/e2e/tasks/skills/ensemble-production/SKILL-61.yaml`, which
drives a running production through an adapterless service from a probe method, not a TestProduction.
The routing corpus carries the #99 issue title with gold `none`
(`tests/e2e/tasks/routing/corpus.jsonl:106`).

## 3. Fact-by-fact coverage

| Fact    | Topic                                   | iad                                                                                                                                                                                                                                |
| ------- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-1     | extend `%UnitTest.TestProduction`       | Not covered in any skill. Tool description names the class (`mod.rs:4085`). Generators push `%UnitTest.TestCase` (`generate.rs:333`).                                                                                              |
| T-2     | no `TestX` methods                      | Contradicted for this case: `objectscript-unit-test/SKILL.md:68` and both generators say every test method starts with `Test`.                                                                                                     |
| T-3     | `TestControl` drives the run            | Not covered. The parser does pick up `TestControl` as the one result line (`mod.rs:4343`), which is correct but unexplained to the caller.                                                                                         |
| T-4     | `PRODUCTION` required                   | Not covered.                                                                                                                                                                                                                       |
| T-5     | interop namespace                       | Not covered.                                                                                                                                                                                                                       |
| T-6–11  | callbacks                               | Not covered.                                                                                                                                                                                                                       |
| T-12    | real callback order                     | Not covered.                                                                                                                                                                                                                       |
| T-13    | CheckErrors status ignored              | Not covered.                                                                                                                                                                                                                       |
| T-14–16 | IGNOREPRODUCTIONERRORS, MAXWAIT, MINRUN | Not covered, including in the tool description, even though MAXWAIT + MINRUN set the run time against the 60 s timeout.                                                                                                            |
| T-17    | properties                              | Not covered.                                                                                                                                                                                                                       |
| T-18    | `SendRequest`, `TestingEnabled`         | Not covered. `ensemble-production/SKILL.md:577` gives a nonexistent `Ens.Director.SendRequestSync` for the same job (wrong).                                                                                                       |
| T-19–20 | `GetEventLog`, Log array, baseId trap   | Not covered.                                                                                                                                                                                                                       |
| T-21    | other helpers                           | Not covered.                                                                                                                                                                                                                       |
| T-22    | `Run()` / `Debug()`                     | Covered in the tool: `.Run()` for detected subclasses (`mod.rs:1341`). This is correct per the docs. Detection misses indirect subclasses (`mod.rs:1364`).                                                                         |
| T-23    | `%UnitTest.Manager.RunTest`             | Covered: the non-production path uses it. `":Pkg.Class"` runs a TestProduction through RunTest too, because detection is skipped for that form (the probe fails on the colon) and RunTest runs `TestControl` like any test method. |
| T-24    | `^UnitTestRoot`                         | Partly. The `.Run()` path does not set it. The directory path overwrites it with `/tmp/httest/` (`mod.rs:1352`). `CopyFile`/`CompareFiles` defaults depend on it.                                                                  |
| T-25    | report URL, assertion lines             | Partly. Pass/fail of `TestControl` comes back; the failing assertion text and the report URL stay in `raw_output` (`mod.rs:4446`), and `failure_message` is null.                                                                  |
| T-26–28 | worked example                          | Not covered. No eval task or fixture.                                                                                                                                                                                              |
| T-29    | stops the running production            | Not covered anywhere, including the tool description. This matters most for an agent pointed at a dev namespace.                                                                                                                   |
| T-30    | run time                                | Not covered. Default 60 s timeout fits the 22 s default run. MINRUN=30 plus a 40 s SendRequest timeout does not, and the description gives no guidance.                                                                            |
| T-31    | `ProductionNeedsUpdate` check           | Not covered.                                                                                                                                                                                                                       |

### Does `iris_test` run a TestProduction subclass correctly?

- **Detection.** It works for a direct subclass named bare (`Tutorial.ProductionTest`). It misses:
  - a subclass of a project base class (`MyApp.ProdTestBase Extends %UnitTest.TestProduction`);
  - a class whose `Super` lists several classes and only inherits it further up;
  - package patterns and wildcards (no probe at all).

  `%Dictionary.CompiledClass` with `$classmethod(cls,"%Extends","%UnitTest.TestProduction")` would
  catch every case. A missed detection falls back to `RunTest("<bare class>", "/verbose=1/nodelete/noload")`.
  That is the #99 shape. Whether it reports NO_TESTS_FOUND for a bare class name on 2026.2 is
  unsettled.

- **`.Run()` vs RunTest.** Both are right per the docs (T-22, T-23). `.Run()` is literally
  `RunTest(":cls:", "/norecursive/debug=0/recursive=0/noload/run/nodelete")`. The special case is
  not wrong, but it is not needed. iad's own `":Pkg.Class"` form already reaches the same code
  path, and it keeps `/verbose=1` and the correlation token.
- **Start and stop.** The framework starts and stops the production itself (`TestControl`). iad
  does nothing extra, which is correct. iad also warns about nothing: a production already running
  in the namespace is stopped, possibly force-stopped and cleaned, and left stopped (T-29).
- **Results and errors to the caller.** You get pass/fail of `TestControl` only. You do not get
  which callback or assertion failed: `failure_message` is null, and the detail needs
  `iris_get_log(log_id)` and a read of `raw_output`. The tool response never says that.
- **Timeouts.** The HTTP path runs the whole test (at least MAXWAIT + MINRUN, about 22 s) inside a
  single Atelier `/action/query` request. iad's 60 s default covers the defaults. No guidance ties
  `timeout` to MAXWAIT, MINRUN and the `SendRequest` `Time`. What happens server-side after iad
  times out (production left running, scratch class deleted mid-run) is unsettled.

### Does any skill teach an agent to write one?

No. An agent asked to "write a test for my production / business operation" today:

1. loads `objectscript-unit-test`, which only knows `%UnitTest.TestCase` and `Test*` methods;
2. or calls `iris_generate_test` / `iris_generate gen_type=test`, which `%New()` the business host
   and call its methods outside a production;
3. or follows `ensemble-production` "Testing without the Management Portal". That means a TestCase
   that starts the production by hand (or assumes one is running), calls
   `CreateBusinessService`/`ProcessInput`, or calls the nonexistent `Ens.Director.SendRequestSync`.
   It handles no event log, no `BaseLogId` window and no automatic error check, and has no stop.

The hand-written route is the one the tutorial exists to replace (T-3, T-29, T-12).

## 4. Ranked gaps and errors

Ranked by how likely each is to mislead an agent.

1. **Error: `Ens.Director.SendRequestSync` does not exist.** At
   `skills/skills/ensemble-production/SKILL.md:577`. An agent copying it gets
   `<METHOD DOES NOT EXIST>`. Fix (skill text): replace it with
   `##class(EnsLib.Testing.Service).SendTestRequest(target, req, .resp, .session, 1)` and say that it
   needs `TestingEnabled="true"` on the production (or the `TestingEnabled` System Default
   Setting). Better still, point to the TestProduction section from item 2. Add a live claim test
   that the method exists, in the style of 130.
2. **Gap: no skill teaches `%UnitTest.TestProduction`.** Fix (skill text): add a "Testing a
   production with `%UnitTest.TestProduction`" section to `ensemble-production`, with a pointer from
   `objectscript-unit-test`. It should cover:
   - extend the class, set `PRODUCTION`, and write no `Test*` methods;
   - the real callback order (T-12);
   - `SendRequest(config, req, .resp, 1, secs)` and `TestingEnabled`;
   - `CheckResults(.Log, New)`, which gets `infouser` entries since `BaseLogId`;
   - `IGNOREPRODUCTIONERRORS` / `CheckErrors` running after stop, with its status ignored, so
     assertions are what count;
   - `GetEventLog("error", "", ..BaseLogId, .err, .n)`, passing `..BaseLogId` and not `""`, and
     killing the array first;
   - MAXWAIT and MINRUN cost;
   - "it stops the running production";
   - running it with `iris_test(pattern="Pkg.Class")`.

   Each claim needs a live test on `iris-dev-iris` in `USER` or `BENCHMARK` (both interop-enabled).

3. **Gap: generators and `objectscript-unit-test` push `%UnitTest.TestCase` for business hosts.**
   At `generate.rs:330-336`, `info.rs:808` and `objectscript-unit-test/SKILL.md:4,68`. Fix (tool
   change): when the target class `%Extends` `Ens.Production`, `Ens.BusinessHost` or the message
   classes, switch to a TestProduction prompt (PRODUCTION parameter, callbacks, `SendRequest`). For
   a production, the target itself goes in PRODUCTION. Fix (skill text): add a one-line branch in
   `objectscript-unit-test`, "testing a production or its hosts → `%UnitTest.TestProduction`, no
   `Test*` methods".
4. **Gap: `iris_test` does not warn that a TestProduction stops the running production.** (T-29)
   Fix (tool change):
   - check `Ens.Director.GetProductionStatus` in the namespace before `.Run()`;
   - if a different production is running, refuse unless the caller passes an explicit opt-in, or
     at least return a `warning` and the name of the production that was stopped;
   - add the fact to the tool description and the `ensemble-production` safety rules.
5. **Gap: failure detail does not reach the caller.** At `mod.rs:4350-4355`. Fix (tool change): for
   failed methods, collect the `(failed)  <<==== **FAILED**` assertion lines (and, for
   TestProduction, the `LogMessage:Error in Event Log:` lines from `TestProduction.cls:941`) into
   `failure_message` or a `failed_assertions` array. Return the `%UnitTest.Portal` report URL /
   result index. This also affects plain TestCase runs, if the missing `--` is confirmed.
6. **Gap: detection misses indirect subclasses.** At `mod.rs:1360-1366`. Fix (tool change): probe
   with `%Dictionary.CompiledClass` and `$classmethod(c,"%Extends","%UnitTest.TestProduction")`. Or
   drop the special case and always run a single class as `RunTest(":"_cls, ...)`, which runs
   `TestControl` the same way and keeps `/verbose=1` and the token. Add a live test with a
   two-level subclass.
7. **Gap: no live, binary or eval coverage.** Fix:
   - (live test) a `#[ignore]` integration test that puts the tutorial's operation, production
     (with `TestingEnabled="true"`) and test class in `USER`, runs `iris_test`, asserts
     `TestControl` passed, asserts a deliberately failing variant reports failed with the assertion
     text, and deletes the classes;
   - (eval task) a held-out ladder task, "write and run a production test for
     `Bench138.Echo`", graded on: extends `%UnitTest.TestProduction`; no `Test*` methods;
     `iris_test` reports `TestControl` passed; no production left running.
8. **Gap: timeout guidance.** (T-15, T-16, T-30) Fix (tool description and skill):
   - a TestProduction takes at least MAXWAIT + MINRUN + ~3 s plus each `SendRequest` `Time`, so set
     `timeout` above that;
   - MAXWAIT is a fixed wait at start, not only a cap;
   - consider having iad read `MAXWAIT`/`MINRUN` from `%Dictionary.CompiledParameter` and raise the
     effective timeout or warn.
9. **Gap: `docs/tools.md:553-569` is stale.** No `test_type` or `server` row, no TestProduction
   note, and a wrong `namespace` default. Fix: docs.
10. **Minor: the directory path overwrites `^UnitTestRoot`.** At `mod.rs:1352`. This affects
    TestProduction `CopyFile`/`CompareFiles` defaults in later runs. Fix: save and restore it, or
    document it.
11. **Tutorial defects an agent may copy.** `%UnitTest.TestManager` (T-23), the misplaced `}` in
    `TTEP_ExampleOperation` (T-27), the CheckErrors status that does nothing (T-13), and the `""`
    baseId (T-19). Fix (skill text): name the right forms. The doc errors could be drafted for
    InterSystems Documentation, not filed.

## 5. Not settled

All of these need a live run, and this task forbade writes to IRIS:

- Whether `execute_via_generator` (Atelier `/action/query`, in a CSP process inside a SQL SELECT) can
  run `Ens.Director.StartProduction` and complete a TestProduction end to end, and whether the
  private web server or gateway cuts a 22 s or longer request before iad's 60 s timeout.
- What happens server-side when iad times out mid-run: whether the production is left running, and
  whether `ScratchGuard` deleting the scratch class during execution matters.
- Whether `RunTest("Pkg.Class", "/verbose=1/nodelete/noload")` (a bare class name, no colon) finds
  the class on 2026.2 or reports NO_TESTS_FOUND. This decides how bad a missed detection (item 6)
  is.
- Whether `failure_message` is null for every failed test. The Manager source has no `--`, but
  I did not observe a failing run.
- Whether `Run()` really needs `^UnitTestRoot` defined on 2026.2, as the tutorial says.
  `Manager.Root()` has a fallback.
- Whether a production created with the Portal wizard, as in the tutorial, has `TestingEnabled` on.
  The property defaults to `""`, which suggests the tutorial's `SendRequest` fails as written unless
  the reader ticks "Testing Enabled".
