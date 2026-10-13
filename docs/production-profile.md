# Production profile

This is for a security or compliance reviewer deciding whether iris-agentic-dev may run against an IRIS
instance that holds personal or health information (a UAT or LIVE environment). It says what the program
does with data, which settings reduce the risk, and what no setting protects. It describes the binary at the
version you install; check `iris-agentic-dev --version` and the release notes.

## What it is

A local process that speaks the Model Context Protocol over stdio to an AI coding assistant (Claude Code,
VS Code, opencode and others) and talks to IRIS over its HTTP (Atelier REST) interface, or by `docker exec`
for a local container. It does not listen on a network port. It holds no data of its own beyond a short
in-memory log buffer and local files you configure.

## Data flow

| From          | To                                      | When                                                                                      | What travels                                      |
| ------------- | --------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------- |
| the assistant | this process (stdio)                    | every tool call                                                                           | tool name and arguments                           |
| this process  | the assistant (stdio)                   | every tool result                                                                         | whatever IRIS returned for that call              |
| this process  | the configured IRIS instance            | every tool call that needs IRIS                                                           | the request, the configured username and password |
| this process  | `raw.githubusercontent.com`             | only on `skill install`/community-skill commands you run                                  | a request for a public skill file; no IRIS data   |
| this process  | `api.github.com`                        | only on package-manifest version resolution you run                                       | a public repository lookup; no IRIS data          |
| this process  | `api.anthropic.com` or `api.openai.com` | only the code-generation tools, and only if `IRIS_GENERATE_CLASS_MODEL` and a key are set | the prompt for the generated class                |

I found no other outbound destination in the source. There is no telemetry upload and no update check. The
`OPENAI_API_KEY`/`ANTHROPIC_API_KEY` variables are read only by the code-generation tools; unset them and
that route is closed. Skills are text files compiled into the binary.

**The assistant is the larger data path.** Everything a tool returns goes to the model provider behind your
assistant, under that provider's terms. This program cannot see or control that hop. The decision about
whether PHI may reach that provider is yours and is separate from this program.

## Settings that reduce the risk

Put these in `.iris-agentic-dev.toml` at the repository root (or the user config), one `[policy.<server>]`
block per connection. The server name is the one you gave the connection.

```toml
[policy.prod-live]
# Only the categories the task needs. No admin, no execute, no source_control.
allow = ["compile", "search", "docs", "skill"]
# live: the most restrictive template. dev is the default and is permissive.
mcpTemplate = "live"
# block: journal_search and iris_message_body, which return whole records, are refused.
dataPolicy = "block"
# Adds to the built-in list of globals that writes and kills may not touch. It does not stop reads.
globalBlocklist = ["^AppHealthData"]
# Write an audit record for every tool call (one-time setup in docs/agent-attribution.md).
irisAudit = true
```

Also:

- **Read-only mode.** Leave `IRIS_WRITE_TOOLS_ENABLED` unset or `false`. The destructive and admin tiers
  (`IRIS_DESTRUCTIVE_TOOLS_ENABLED`, `IRIS_ADMIN_TOOLS`) are off by default; leave them off.
- **Least-privilege IRIS account.** Create an account whose roles cannot read the protected tables and
  globals, and configure that one. This is the control that holds when everything else fails, because the
  server cannot do more than the account can. Do not use `_SYSTEM` or a `%All` account.
- **Use TLS.** Set the connection scheme to `https` and leave `IRIS_TLS_VERIFY` on. Do not set `IRIS_INSECURE`.
- **No skills if you do not want them.** `IRIS_NO_SKILLS=true` removes the skill, knowledge-base and learning
  tools from the tool list.
- **No code-generation route.** Leave `IRIS_GENERATE_CLASS_MODEL`, `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`
  unset in the environment of the process.
- **Credentials.** Keep them in the OS credential store or environment, not in the TOML file in the repository.
- **Audit.** `irisAudit` writes the caller marker (see `docs/agent-attribution.md`) so IRIS's own audit log
  shows which assistant made each call.

## What no setting protects

- **`iris_query` and `iris_execute` are free-form.** They run SQL or ObjectScript the assistant composes.
  The protected-data checks look at global names and tool categories; they do not parse every query, and
  there is no automatic redaction of results from these tools. A permitted account that can select from a
  patient table can have that data returned to the assistant. Leave these tools out of `allow` if that matters.
- **The PHI gate is a speed bump, not a lock.** It stops the accidental case. `acknowledgePhi` removes it for
  a call, and indirection in ObjectScript (`Kill @name`) is not seen by a text check.
- **`dataPolicy = "redact"` is partial.** HL7 v2 field-level redaction is not delivered; do not rely on it.
- **The model provider's side.** Prompt injection from data the assistant reads (a field containing
  instructions) can steer tool calls. The policy limits what those calls can do; it does not prevent them.
- **Binaries are unsigned.** The macOS build carries an ad-hoc signature and the Windows release binary
  carries none. Verify the SHA-256 against the release or Homebrew formula, or build from source at a tag.

## Evidence

- Dependency scans and their results: `SECURITY.md`. The SBOM for each release is
  `iris-agentic-dev-<version>.cdx.json` on the release page.
- Gate behaviour is covered by tests that run against a live IRIS container (`cargo test --features testing`).
- No independent penetration test has been done.

## Suggested rollout

1. Run it against a non-production copy first with the profile above and read the audit records.
2. Connect production with an account limited to what the task needs, `mcpTemplate = "live"`, read-only.
3. Re-review when the version changes: new tools are added over time, and `allow` is the list that bounds them.
