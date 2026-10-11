"""Which build a measurement ran against (135 T007).

A session line that does not say which binary and commit it ran against cannot be compared with
another one, and a binary older than the source holds the old embedded skills. The stamp is taken once
at the start of a run and copied onto every session line and into the report.
"""

from __future__ import annotations

import hashlib
import os
import subprocess

#: The trees whose files are compiled into, or read by, the binary under test.
SOURCE_ROOTS = ("crates", "skills")
SOURCE_FILES = ("Cargo.toml", "Cargo.lock")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


class BuildRefused(RuntimeError):
    """The build is not one a measurement may run against."""


def _git(repo: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise BuildRefused(
            f"git {' '.join(args)} failed: {result.stderr.strip()[:200]}"
        )
    return result.stdout


def _tracked_sources(repo: str) -> list[str]:
    names = _git(repo, "ls-files", "-z").split("\0")
    return [
        name
        for name in names
        if name
        and (name.split("/")[0] in SOURCE_ROOTS or name in SOURCE_FILES)
        and os.path.isfile(os.path.join(repo, name))
    ]


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_stamp(binary: str | None, repo: str = REPO_ROOT) -> dict:
    """Binary path, sha256 and version, the commit, whether tracked files are modified, and whether
    any source file is newer than the binary."""
    from tests.e2e.skill_eval.provenance import binary_version

    if not binary or not os.path.isfile(binary):
        raise BuildRefused(
            f"no binary to measure ({binary!r}). Build one and pass IAD_BINARY=$PWD/target/debug/"
            "iris-agentic-dev; a session without it would run whatever is on PATH"
        )
    built = os.path.getmtime(binary)
    newer = sorted(
        name
        for name in _tracked_sources(repo)
        if os.path.getmtime(os.path.join(repo, name)) > built
    )
    dirty = bool(_git(repo, "status", "--porcelain", "--untracked-files=no").strip())
    return {
        "binary": binary,
        "binary_sha256": _sha256(binary),
        "binary_version": binary_version(binary),
        "commit": _git(repo, "rev-parse", "HEAD").strip(),
        "dirty": dirty,
        "binary_stale": bool(newer),
        "newer_source": newer[:10],
    }


def assert_current(stamp: dict, *, require_clean: bool = False) -> None:
    """Refuse a stale binary always, and a modified tree when the run is a verdict run."""
    if stamp["binary_stale"]:
        raise BuildRefused(
            f"{stamp['binary']} is older than {', '.join(stamp['newer_source'][:3])}, so it does not "
            "contain the current source or the current embedded skills. Run `cargo build` first"
        )
    if require_clean and stamp["dirty"]:
        raise BuildRefused(
            "the tree has uncommitted changes to tracked files, so the commit in the record does "
            "not describe what ran. Commit them, then start the run"
        )
