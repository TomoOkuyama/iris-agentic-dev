"""The security documents a reviewer reads have to exist and be true.

TPRM-6601 and TPRM-6602 asked for a disclosure policy, fix timelines, a notification route, an SBOM and
a statement of what leaves the machine. Prose can drift from the code it describes, so the checkable
parts are checked: the policy keys in the production profile are parsed with a real TOML parser and
compared with the keys the config loader accepts, and the SBOM has to be built and attached by the
release workflow.
"""

import os
import re
import tomllib

import pytest

yaml = pytest.importorskip("yaml")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


# --- SECURITY.md ---------------------------------------------------------------------------------------


def test_security_md_names_a_way_to_report_and_what_happens_next():
    text = read("SECURITY.md")
    assert "tdyar@intersystems.com" in text
    for heading in ("## Reporting a vulnerability", "## Supported versions", "## What to expect"):
        assert heading in text, heading


def test_security_md_states_a_target_for_every_severity():
    text = read("SECURITY.md")
    for severity in ("Critical", "High", "Medium", "Low"):
        assert re.search(rf"\|\s*{severity}\s*\|", text), f"no target row for {severity}"
    assert "target" in text.lower() and "not a guarantee" in text.lower()


def test_security_md_says_how_users_hear_about_a_fix():
    text = read("SECURITY.md").lower()
    assert "release notes" in text and "security advisory" in text


def test_security_md_points_at_the_scans_and_the_sbom():
    text = read("SECURITY.md")
    for needle in ("cargo audit", "npm audit", "SBOM", "docs/production-profile.md"):
        assert needle in text, needle


# --- the SBOM ------------------------------------------------------------------------------------------


def _release():
    return yaml.safe_load(read(".github", "workflows", "release.yml"))


def test_the_release_workflow_builds_a_cyclonedx_sbom():
    jobs = _release()["jobs"]
    steps = " ".join(
        step.get("run", "") for job in jobs.values() for step in job.get("steps", [])
    )
    assert "cargo cyclonedx" in steps and "--locked" in steps


def test_the_sbom_is_attached_to_the_release():
    jobs = _release()["jobs"]
    release = jobs["release"]
    assert "sbom" in release["needs"], "the release must wait for the SBOM"
    attached = " ".join(
        str(step.get("with", {}).get("files", "")) for step in release["steps"]
    )
    assert ".cdx.json" in attached


# --- the production profile ----------------------------------------------------------------------------


def _toml_blocks():
    blocks = re.findall(r"```toml\n(.*?)```", read("docs", "production-profile.md"), re.S)
    assert blocks, "the profile shows no TOML"
    return [tomllib.loads(block) for block in blocks]


def _accepted_policy_keys():
    source = read("crates", "iris-agentic-dev-core", "src", "iris", "workspace_config.rs")
    struct = source[source.index("pub struct ConnectionPolicyRaw") :]
    struct = struct[: struct.index("\n}\n")]
    renamed = set(re.findall(r'rename = "([^"]+)"', struct))
    fields = set(re.findall(r"pub (\w+):", struct))
    return renamed | fields


def _categories():
    source = read("crates", "iris-agentic-dev-core", "src", "iris", "workspace_config.rs")
    enum = source[source.index("pub enum ToolCategory") :]
    enum = enum[: enum.index("}")]
    return {
        re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        for name in re.findall(r"^\s+([A-Z]\w+),", enum, re.M)
    }


def test_every_policy_key_in_the_profile_is_one_the_loader_accepts():
    accepted = _accepted_policy_keys()
    assert {"mcpTemplate", "dataPolicy", "irisAudit", "allow"} <= accepted
    seen = set()
    for block in _toml_blocks():
        for name, policy in block.get("policy", {}).items():
            unknown = set(policy) - accepted
            assert not unknown, f"[policy.{name}] has keys the loader would silently drop: {unknown}"
            seen |= set(policy)
    assert {"mcpTemplate", "dataPolicy", "irisAudit", "allow"} <= seen, seen


def test_the_profile_uses_real_categories_and_values():
    categories = _categories()
    assert "source_control" in categories and "kb" in categories
    for block in _toml_blocks():
        for policy in block.get("policy", {}).values():
            assert set(policy.get("allow", [])) <= categories
            if "mcpTemplate" in policy:
                assert policy["mcpTemplate"].lower() in {"dev", "test", "live"}
            if "dataPolicy" in policy:
                assert policy["dataPolicy"] in {"block", "allow", "redact"}


def test_the_profile_names_every_place_the_binary_can_send_data():
    text = read("docs", "production-profile.md")
    for needle in (
        "api.anthropic.com",
        "api.openai.com",
        "raw.githubusercontent.com",
        "algolia.net",
        "IRIS_NO_SKILLS",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        assert needle in text, needle


def test_the_profile_says_what_it_does_not_protect():
    text = read("docs", "production-profile.md").lower()
    for needle in ("iris_query", "no automatic redaction", "speed bump", "unsigned"):
        assert needle in text, needle


# --- checksums and the no-download install -------------------------------------------------------------

BINARIES = (
    "iris-agentic-dev-linux-x86_64",
    "iris-agentic-dev-linux-aarch64",
    "iris-agentic-dev-macos-arm64",
    "iris-agentic-dev-macos-x86_64",
    "iris-agentic-dev-windows-x86_64.exe",
)


def _release_steps():
    return _release()["jobs"]["release"]["steps"]


def test_the_release_computes_sha256sums_over_every_binary_it_attaches():
    steps = _release_steps()
    sums = [s for s in steps if "sha256sum" in s.get("run", "") and "SHA256SUMS" in s.get("run", "")]
    assert sums, "no step writes SHA256SUMS"
    script = sums[0]["run"]
    for name in BINARIES:
        assert name in script, f"SHA256SUMS would leave out {name}"
    order = [i for i, s in enumerate(steps) if s is sums[0] or "action-gh-release" in s.get("uses", "")]
    assert order[0] == steps.index(sums[0]) < order[-1], "the sums must be written before the upload"


def test_sha256sums_is_attached_to_the_release():
    attached = " ".join(
        str(step.get("with", {}).get("files", "")) for step in _release_steps()
    )
    assert "SHA256SUMS" in attached


def test_security_md_does_not_send_readers_to_a_checksum_that_is_not_there():
    text = read("SECURITY.md")
    assert "SHA256SUMS" in text
    assert "verify the SHA-256 against the release or Homebrew" not in " ".join(text.split())


def test_the_profile_gives_a_pinned_install_with_a_check_and_no_download():
    text = read("docs", "production-profile.md")
    flat = " ".join(text.split())
    assert "releases/download/v" in text and "releases/latest" in text, "pin a version, and say why not latest"
    assert "sha256sum -c" in text
    assert "iris-agentic-dev.serverPath" in text
    assert "no download" in flat.lower()
