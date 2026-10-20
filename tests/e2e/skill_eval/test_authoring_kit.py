"""The task authoring kit and `quality_checks` — 135 T004 and T005, written before the code.

A skill task lives in `tests/e2e/tasks/skills/<skill>/<TASK>.yaml`. The directory name is the skill
the task measures, so a task cannot be filed under one skill and measure another. Quality checks are
extra ObjectScript checks that score a fraction beside the pass/fail check; they never replace it.
"""

from __future__ import annotations

import textwrap

import pytest

from tests.e2e.skill_eval import graded_task
from tests.e2e.skill_eval.graded_task import CheckBroken, CorpusInvalid, load_task

BASE = textwrap.dedent(
    """\
    id: {id}
    prompt: |
      Do the thing.
    skill: {skill}
    fixtures:
      - name: Bench.K
        content: |
          Class Bench.K {{ }}
    check: |
      write $select(1:"PASS",1:"FAIL")
    solution:
      - name: Bench.K
        content: |
          Class Bench.K {{ ClassMethod M() {{ }} }}
    """
)


def write(tmp_path, task_id="SKILL-90", skill="objectscript-tdd", extra="", sub=None):
    directory = tmp_path / (sub if sub is not None else skill)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{task_id}.yaml"
    path.write_text(BASE.format(id=task_id, skill=skill) + extra)
    return path


# --- the directory ------------------------------------------------------------------------------


def test_authored_tasks_are_loaded_from_per_skill_subdirectories(tmp_path):
    write(tmp_path, "SKILL-90", "objectscript-tdd")
    write(tmp_path, "SKILL-91", "iris-sql")
    tasks = graded_task.load_authored(str(tmp_path))
    assert [(t.id, t.skill) for t in tasks] == [
        ("SKILL-90", "objectscript-tdd"),
        ("SKILL-91", "iris-sql"),
    ]


def test_a_task_filed_under_another_skills_directory_is_refused(tmp_path):
    write(tmp_path, "SKILL-90", skill="iris-sql", sub="objectscript-tdd")
    with pytest.raises(CorpusInvalid) as caught:
        graded_task.load_authored(str(tmp_path))
    assert "iris-sql" in str(caught.value) and "objectscript-tdd" in str(caught.value)


def test_the_older_judged_fixtures_in_the_same_tree_are_not_tasks(tmp_path):
    write(tmp_path, "SKILL-90", "objectscript-tdd")
    (tmp_path / "objectscript-tdd" / "eval.yaml").write_text("skill: objectscript-tdd\n")
    (tmp_path / "targeted").mkdir()
    (tmp_path / "targeted" / "x.yaml").write_text("not: a task\n")
    assert [t.id for t in graded_task.load_authored(str(tmp_path))] == ["SKILL-90"]


def test_a_missing_authoring_root_is_empty_not_an_error(tmp_path):
    assert graded_task.load_authored(str(tmp_path / "nope")) == ()


def test_a_loose_file_in_the_root_is_refused(tmp_path):
    (tmp_path / "SKILL-90.yaml").write_text("id: SKILL-90\n")
    with pytest.raises(CorpusInvalid):
        graded_task.load_authored(str(tmp_path))


def test_all_tasks_includes_the_authored_ones_and_refuses_a_duplicate_id(
    tmp_path, monkeypatch
):
    write(tmp_path, "SKILL-01", "objectscript-tdd")
    monkeypatch.setattr(graded_task, "AUTHORED_DIR", str(tmp_path))
    with pytest.raises(CorpusInvalid) as caught:
        graded_task.all_tasks()
    assert "SKILL-01" in str(caught.value)


def test_the_committed_authoring_root_is_where_the_goal_says():
    assert graded_task.AUTHORED_DIR.endswith("tests/e2e/tasks/skills")


# --- quality_checks -----------------------------------------------------------------------------

QUALITY = textwrap.dedent(
    """\
    quality_checks:
      - name: other-method-unchanged
        check: |
          write $select(1:"PASS",1:"FAIL")
      - name: compiles-clean
        check: |
          write $select(0:"PASS",1:"FAIL")
    """
)


def test_quality_checks_are_parsed_in_order(tmp_path):
    task = load_task(str(write(tmp_path, extra=QUALITY)))
    assert [q.name for q in task.quality_checks] == [
        "other-method-unchanged",
        "compiles-clean",
    ]


def test_a_task_without_quality_checks_has_none(tmp_path):
    assert load_task(str(write(tmp_path))).quality_checks == ()


@pytest.mark.parametrize(
    "extra, fragment",
    [
        ("quality_checks:\n  - check: write 1\n", "name"),
        ('quality_checks:\n  - name: a\n    check: write "PASS"\n', "FAIL"),
        (
            "quality_checks:\n  - name: a\n    check: write $H,\"PASS\",\"FAIL\"\n",
            "$H",
        ),
        (
            'quality_checks:\n  - name: a\n    check: write "PASS","FAIL"\n'
            '  - name: a\n    check: write "PASS","FAIL"\n',
            "twice",
        ),
        ("quality_checks: not-a-list\n", "list"),
    ],
)
def test_a_malformed_quality_check_is_refused(tmp_path, extra, fragment):
    with pytest.raises(CorpusInvalid) as caught:
        load_task(str(write(tmp_path, extra=extra)))
    assert fragment in str(caught.value)


def test_quality_score_is_the_fraction_that_passed():
    assert graded_task.quality_score({"a": True, "b": False, "c": True, "d": True}) == 0.75
    assert graded_task.quality_score({"a": True}) == 1.0
    assert graded_task.quality_score({}) is None


def test_a_quality_check_that_did_not_answer_is_left_out_of_the_fraction():
    assert graded_task.quality_score({"a": True, "b": None}) == 1.0
    assert graded_task.quality_score({"a": None}) is None


def test_run_quality_runs_each_check_and_marks_a_broken_one_none(tmp_path, monkeypatch):
    task = load_task(str(write(tmp_path, extra=QUALITY)))
    answers = {"PASS": "PASS", "FAIL": "FAIL"}
    seen = []

    def fake_iad(args, namespace):
        seen.append(args[1])
        if 'write $select(0:"PASS"' in args[1]:
            raise CheckBroken("exited 1")
        return answers["PASS"]

    monkeypatch.setattr(graded_task, "_iad", fake_iad)
    results = graded_task.run_quality(task)
    assert results == {"other-method-unchanged": True, "compiles-clean": None}
    assert len(seen) == 2


def test_run_quality_of_a_task_without_checks_runs_nothing(tmp_path, monkeypatch):
    task = load_task(str(write(tmp_path)))
    monkeypatch.setattr(graded_task, "_iad", lambda *a: pytest.fail("ran a check"))
    assert graded_task.run_quality(task) == {}


def test_validate_live_demands_the_reference_pass_every_quality_check(
    tmp_path, monkeypatch
):
    task = load_task(str(write(tmp_path, extra=QUALITY)))
    monkeypatch.setattr(graded_task, "run_teardown", lambda t: None)
    monkeypatch.setattr(graded_task, "reset_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "apply_documents", lambda *a, **k: None)
    state = {"applied_solution": False}
    monkeypatch.setattr(
        graded_task, "apply_documents", lambda docs, ns: state.update(applied_solution=docs == task.solution)
    )
    monkeypatch.setattr(graded_task, "run_check", lambda t: state["applied_solution"])
    monkeypatch.setattr(
        graded_task,
        "run_quality",
        lambda t: {"other-method-unchanged": True, "compiles-clean": False},
    )
    with pytest.raises(CorpusInvalid) as caught:
        graded_task.validate_live(task)
    assert "compiles-clean" in str(caught.value)


def test_run_one_records_quality_beside_pass(monkeypatch):
    from tests.e2e.skill_eval import pilot
    from tests.e2e.skill_eval.arms import TOOLS
    from tests.e2e.skill_eval.test_pilot import RecordingDriver, fake_task

    task = fake_task("FAKE-01")
    task = type(task)(
        **{
            **task.__dict__,
            "quality_checks": (graded_task.QualityCheck("a", 'write "PASS","FAIL"'),),
        }
    )
    monkeypatch.setattr(graded_task, "validate_live", lambda _t: None)
    monkeypatch.setattr(graded_task, "reset_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "apply_documents", lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "list_classes", lambda *a, **k: set())
    monkeypatch.setattr(graded_task, "run_teardown", lambda t: None)
    monkeypatch.setattr(graded_task, "run_check", lambda _t: False)
    monkeypatch.setattr(graded_task, "run_quality", lambda t: {"a": True})
    run = pilot.run_one(
        task,
        TOOLS,
        openai_api_key="sk-test",
        skill_names=(),
        iris_host="localhost",
        iris_web_port="52780",
        iris_container="iris-dev-iris",
        driver=RecordingDriver(),
    )
    assert run.passed is False
    assert run.quality == 1.0
    assert run.quality_detail == {"a": True}


# --- the fingerprint a run records so a changed task is visible -------------------------------------


def test_the_fingerprint_changes_with_the_check_the_prompt_or_a_fixture(tmp_path):
    base = load_task(str(write(tmp_path)))
    again = load_task(str(write(tmp_path)))
    assert graded_task.task_fingerprint(base) == graded_task.task_fingerprint(again)
    for field, value in (
        ("prompt", "other"),
        ("check", 'write $select(0:"PASS",1:"FAIL")'),
        ("fixtures", (graded_task.Document("Bench.K", "x"),)),
        ("quality_checks", (graded_task.QualityCheck("a", 'write "PASS","FAIL"'),)),
    ):
        changed = type(base)(**{**base.__dict__, field: value})
        assert graded_task.task_fingerprint(changed) != graded_task.task_fingerprint(base), field


def test_every_session_line_can_carry_the_task_fingerprint():
    from tests.e2e.skill_eval import ladder

    line = ladder.session_line(
        {"task_id": "T"}, side="holdout", build=None, fingerprints={"T": "abc"}
    )
    assert line["task_fingerprint"] == "abc"
