# 0002: The improvement loop is an engine and a project adapter

Date: 2026-10-12. Status: accepted.

## Context

The loop that measures and improves iad had grown into three command-line tools (`skill_eval`,
`ladder`, `optimize`) with about twenty flags between them and no single place that said what to do
next. Its first simple front end, `improve status` and `improve next`, hard-coded this project's paths,
container names, workflow name and arm names. Tom wants the same loop for his other projects, so
anything that names iad in the engine would be rewritten each time.

## Decisions

- **The engine knows the loop and nothing about the project.** It lives in `.improve/engine/` and may
  not mention iad, IRIS, its containers or its arm names. A test fails if it does.
- **One file, `.improve/project.toml`, holds every project fact:** where run records and tasks live,
  what the two arms are called and labelled, which scheduled workflow is the nightly, how to check one
  task, how to ask whether its environment is up, and the spend caps. It is the only file a new project
  writes.
- **An unknown key in the adapter is an error.** A misspelt key must not fall back to a default and
  leave the loop quietly measuring the wrong thing.
- **The engine's input is a documented record,** not the harness that produced it. The contract is in
  `.improve/README.md`. A project whose harness writes something else adds a converter; the engine does
  not grow a second reader.
- **The directory is self-contained.** Copying `.improve/` into another project, rewriting
  `project.toml`, and running `.improve/improve status` is the whole install. Its tests, glossary and
  README travel with it.
- **The verbs are `status`, `next`, and later `try` and `week`.** The first two are free and stay free;
  a test fails if they could start a process of their own. The two that spend show an estimate, ask, and
  stop at the cap.

## Considered options

- **Extend the three existing tools with a wrapper.** It would be quick and iad-specific. It leaves
  every other project to copy and edit the wrapper, which is how the engine would fork.
- **A shared package in its own repository now.** Right in the end, but it needs a second project to
  show what belongs in the engine, and the location is Tom's to choose. A self-contained directory moves
  there by copying.
- **Configuration in code (a Python module per project).** More flexible, but then a project can put
  logic in its adapter and the engine can no longer be tested against a made-up project.
- **Keep the three tools and document them.** The documentation would be correct and nobody would read
  it; the complaint was that the interface needed to be simpler.

## Consequences

- iad's own loop machinery (`tests/e2e/skill_eval/`) stays where it is and keeps producing the run
  records. `.improve/` reads them and does not replace the harness.
- Adding a verb means adding it to the engine and a test, not a flag to one of three tools.
- The engine depends on PyYAML for task files and on Python 3.11 for `tomllib`. A project on older Python
  has to upgrade or vendor `tomli`.
- This holds while two arms are the shape of the experiment. A three-arm comparison would need an
  engine change, and that change is the second project's reason to extract the engine into a shared
  home.
