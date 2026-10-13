# Security policy

iris-agentic-dev is an open-source (MIT) MCP server that lets an AI coding assistant work against an
InterSystems IRIS instance. It is maintained by Thomas Dyar (InterSystems) with community contributors. It
is a community project: there is no support contract and nothing here is a service-level guarantee.

## Reporting a vulnerability

Email **<tdyar@intersystems.com>** with "iris-agentic-dev security" in the subject. Please include the version
(`iris-agentic-dev --version`), what you did, what happened, and what you expected. Do not open a public
issue for a vulnerability.

Reports in scope: anything that lets a caller get past a safety gate (the write and destructive tiers, the
data-policy and protected-data checks, the system-global blocklist, a connection's `[policy.*]` block),
leak or mishandle a credential, run code or reach data the configured IRIS account could not, or take over
the process through the MCP interface.

Out of scope: what a configured, authorised IRIS account can already do; the behaviour of the AI assistant or
model provider you connect (see `docs/production-profile.md`); vulnerabilities in IRIS itself (report those to
InterSystems through the usual channel).

## Supported versions

Only the latest release receives security fixes. Releases are listed at
<https://github.com/intersystems-community/iris-agentic-dev/releases>.

## What to expect

- An acknowledgement within 5 business days.
- An assessment of severity and a plan, shared with the reporter.
- A fix, a release and a notice, with credit to the reporter if they want it.
- Coordinated disclosure: please give me up to 90 days before publishing details, and I will tell you
  sooner if a fix ships earlier.

Targets for a fix to be released, counted from the day I confirm the report. They are targets and not a guarantee:

| Severity | Meaning                                                                                      | Target to release a fix |
| -------- | -------------------------------------------------------------------------------------------- | ----------------------- |
| Critical | Bypass of a safety gate or credential disclosure that needs no special access                 | 14 days                 |
| High     | The same, but needs a configuration or access the attacker is unlikely to have                | 30 days                 |
| Medium   | Hardening gaps and denial of service                                                          | the next release        |
| Low      | Anything else                                                                                | best effort             |

## How you hear about a fix

Every release has release notes on GitHub. A security fix is named as one there and, once fixed, is also
published as a GitHub security advisory. The VS Code extension updates through the Marketplace, and the
binary through GitHub releases and Homebrew. There is no mailing list: watch the repository's releases, or
ask to be told directly if you operate it in a regulated environment.

## What is tested before a release

- Every pull request runs `cargo fmt`, `cargo clippy` with warnings as errors, and the full Rust test suite
  against a live IRIS container, including regression tests for each safety-gate bypass fixed so far.
- Every pull request, every push to master and a weekly schedule run `cargo audit` against the locked Rust
  dependencies and `npm audit` against the VS Code extension's production dependencies. A known
  vulnerability fails the job.
- Each release publishes a CycloneDX SBOM (`iris-agentic-dev-<version>.cdx.json`) listing every locked
  dependency.

Not done: there is no independent penetration test, no fuzzing and no static-analysis service beyond the
compiler and clippy.

## Release integrity

The Homebrew formula pins a SHA-256 for each binary. The published binaries are not signed with a publisher
certificate (the macOS build carries an ad-hoc signature, and the Windows release binary is unsigned). To
avoid trusting a download, build from source at a tagged release: `cargo build --locked --release -p
iris-agentic-dev`.

## Running it against real data

Read `docs/production-profile.md` before pointing it at an instance that holds personal or health
information. It lists what leaves the machine, the settings that reduce the risk, and what no setting
protects.
