"""Which build a session ran against — 135 T007, written before the code.

A baseline measured last week is not a baseline. Every session line in a run file names the binary
(path, sha256, version) and the commit, and a binary older than the source it should contain is
refused, because `cargo build` forgotten after a skill edit means the embedded skill is the old one.
"""

from __future__ import annotations

import os
import subprocess

import pytest


def _git(repo, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "crates").mkdir()
    (tmp_path / "crates" / "a.rs").write_text("fn main() {}\n")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "S.md").write_text("skill\n")
    (tmp_path / "notes.md").write_text("not source\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


@pytest.fixture
def binary(tmp_path_factory):
    path = tmp_path_factory.mktemp("bin") / "iris-agentic-dev"
    path.write_text("#!/bin/sh\necho 'iris-agentic-dev 9.9.9'\n")
    path.chmod(0o755)
    return str(path)


def test_the_stamp_names_binary_version_sha_and_the_commit(repo, binary):
    from tests.e2e.skill_eval.build_stamp import build_stamp

    stamp = build_stamp(binary, repo=str(repo))
    assert stamp["binary"] == binary
    assert stamp["binary_version"] == "9.9.9"
    assert len(stamp["binary_sha256"]) == 64
    assert len(stamp["commit"]) == 40
    assert stamp["dirty"] is False


def test_a_changed_tracked_file_makes_the_tree_dirty_and_an_untracked_one_does_not(
    repo, binary
):
    from tests.e2e.skill_eval.build_stamp import build_stamp

    (repo / "stray.txt").write_text("untracked\n")
    assert build_stamp(binary, repo=str(repo))["dirty"] is False
    (repo / "crates" / "a.rs").write_text("fn main() { 1; }\n")
    assert build_stamp(binary, repo=str(repo))["dirty"] is True


def test_a_binary_older_than_the_source_is_stale(repo, binary):
    from tests.e2e.skill_eval.build_stamp import build_stamp

    os.utime(binary, (1_000_000, 1_000_000))
    stamp = build_stamp(binary, repo=str(repo))
    assert stamp["binary_stale"] is True
    assert (
        "crates/a.rs" in stamp["newer_source"] or "skills/S.md" in stamp["newer_source"]
    )


def test_a_binary_newer_than_the_source_is_current(repo, binary):
    from tests.e2e.skill_eval.build_stamp import build_stamp

    future = os.path.getmtime(repo / "crates" / "a.rs") + 100
    os.utime(binary, (future, future))
    stamp = build_stamp(binary, repo=str(repo))
    assert stamp["binary_stale"] is False


def test_a_file_outside_crates_and_skills_does_not_make_the_binary_stale(repo, binary):
    from tests.e2e.skill_eval.build_stamp import build_stamp

    future = os.path.getmtime(repo / "crates" / "a.rs") + 100
    os.utime(binary, (future, future))
    os.utime(repo / "notes.md", (future + 500, future + 500))
    assert build_stamp(binary, repo=str(repo))["binary_stale"] is False


def test_assert_current_refuses_a_stale_binary_and_names_the_fix(repo, binary):
    from tests.e2e.skill_eval.build_stamp import (
        BuildRefused,
        assert_current,
        build_stamp,
    )

    os.utime(binary, (1_000_000, 1_000_000))
    with pytest.raises(BuildRefused) as caught:
        assert_current(build_stamp(binary, repo=str(repo)))
    assert "cargo build" in str(caught.value)


def test_assert_current_refuses_a_dirty_tree_only_when_asked(repo, binary):
    from tests.e2e.skill_eval.build_stamp import (
        BuildRefused,
        assert_current,
        build_stamp,
    )

    future = os.path.getmtime(repo / "crates" / "a.rs") + 100
    (repo / "skills" / "S.md").write_text("edited\n")
    future = os.path.getmtime(repo / "skills" / "S.md") + 100
    os.utime(binary, (future, future))
    stamp = build_stamp(binary, repo=str(repo))
    assert_current(stamp)
    with pytest.raises(BuildRefused) as caught:
        assert_current(stamp, require_clean=True)
    assert "uncommitted" in str(caught.value)


def test_no_binary_is_refused_not_stamped_as_none(repo):
    from tests.e2e.skill_eval.build_stamp import BuildRefused, build_stamp

    with pytest.raises(BuildRefused):
        build_stamp(None, repo=str(repo))


def test_the_ladder_exposes_require_clean():
    from tests.e2e.skill_eval import ladder

    assert ladder.parse_args(["--require-clean"]).require_clean is True
    assert ladder.parse_args([]).require_clean is False


def test_every_session_line_carries_the_stamp():
    from tests.e2e.skill_eval import ladder

    stamp = {"binary_version": "1.5.0", "commit": "a" * 40}
    line = ladder.session_line(
        {"task_id": "T", "arm": "tools"}, side="holdout", build=stamp
    )
    assert line["build"] == stamp
    assert line["side"] == "holdout"
