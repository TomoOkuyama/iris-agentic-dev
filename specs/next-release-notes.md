# Next release notes (staging)

Baseline: v1.6.1, whose notes are final in `docs/release-notes/v1.6.1.md`. What follows is
staged for the release after it.

I add an entry here as each user-facing change lands, so release notes are not
reconstructed from `git log` at tag time. At release time this drains into
`docs/release-notes/vX.Y.Z.md`, which is what `docs/release-checklist.md` step 4 gates on
and what becomes the GitHub release body via `gh release edit <tag> --notes`. The VS Code
extension's `CHANGELOG.md` is built from those files (#136).

Rules for anything written here:

- Keep the three sections below, in this order, and end the drained file with a
  `vX.Y.Z...vA.B.C` compare link.
- Internal-only work (refactors, test infrastructure, CI) stays out unless a caller can
  observe the difference.
- Name the tool, flag, or file and give the number. "Improved performance" is not an entry;
  "suite went from 254 s to 61 s" is.
- Run `/no-ai-slop` detect on the drained file and fix every finding before publishing.
- First person singular. This is a one-person project.

## What's new

Nothing staged.

## Notable fixes

- **`iris_search` says when it stopped short.** Atelier stops a search at 200 matches unless told
  otherwise, and says so only in a field iad never read, so a search could stop at 200 and look
  complete. iad now sends a limit (`limit`, default 200, up to 10000) and the response carries
  `limit_reached: true` and a `warning` when Atelier hit it. On `%Library.*.cls`, `Quit` stops at
  200 matches in 11 files; with `limit: 1000` it returns 1000 in 43.
- **`iris_search` with `regex: true` searches by pattern.** iad sent `regex=true`, which Atelier
  reads as off, so every regex search was a literal one: `Test.*Passes` looked for the text
  `Test.*Passes`. iad now sends `regex=1`, and wraps the pattern so it matches anywhere in a line,
  as in grep, because Atelier matches a regex against the whole line. `^` and `$` still anchor it.
- **`objectscript-navigation` and `objectscript-repair`** said `iris_symbols(query="ClassName.*")`
  lists a class's members. It matches class names only, and that query returns nothing. Both
  skills now send member lookups to `docs_introspect`, and `objectscript-repair` checks a rename
  with `iris_search`, because a call to a renamed method still compiles and fails only when it
  runs, with `<METHOD DOES NOT EXIST>`.
- **`docs/tools.md`** said `iris_doc put` strips Storage blocks because IRIS 2025.1+ rejects them.
  It never did, and IRIS 2025.3 and 2026.2 both accept a Storage block in a PUT. The guard that
  exists refuses a `put` that would drop a class's Storage block, unless
  `allow_storage_regeneration` is set.

## Breaking changes

Nothing staged.
