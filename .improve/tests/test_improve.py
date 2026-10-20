"""`improve status` and `improve next`, and the adapter that makes them portable.

The engine knows the loop and nothing about the project it runs in: where results live, what the two
arms are called, how to check one task, which workflow is the nightly, all of that is in
`.improve/project.toml`. These tests build a small project in a temp directory, so they prove the
engine on something that is not this repository, and a guard test fails if the engine starts naming
this project.

Both verbs cost nothing and must stay that way; the last tests fail if anything in them could start a
session.
"""

import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest

import improve

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def write_record(
    directory: Path,
    name: str,
    outcomes: dict,
    *,
    measured_at="2026-09-19T06:48:40Z",
    side=None,
    published=None,
    baseline="plain",
    treated="memory",
):
    """`outcomes` maps task id to (baseline passed, treated passed)."""
    runs = []
    for task_id, (base_ok, treated_ok) in outcomes.items():
        for arm, ok in ((baseline, base_ok), (treated, treated_ok)):
            run = {
                "task_id": task_id,
                "arm": arm,
                "passed": ok,
                "tool_calls": 5,
                "seconds": 30.0,
                "timed_out": False,
            }
            if side:
                run["side"] = side
            runs.append(run)
    (directory / name).write_text(
        json.dumps(
            {
                "runs": runs,
                "provenance": {"measured_at": measured_at},
                "published": published
                or [
                    f"{baseline} -> {treated}  lift +0.098 [-0.034, +0.230]  n=40 pairs"
                ],
            }
        )
    )


def task_file(tasks_dir: Path, task_id: str, first_line="Do the thing."):
    sub = tasks_dir / "all"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"{task_id}.yaml").write_text(
        f"id: {task_id}\nprompt: |\n  {first_line}\n  More detail.\n"
    )


def nightly(state="green", when="2026-10-10"):
    return lambda: improve.Nightly(state=state, when=when, detail="")


def make_config(root: Path, **over) -> improve.Config:
    cfg = dict(
        root=root,
        name="demo",
        results_dir=root / "results",
        tasks_dir=root / "tasks",
        ledger=root / "ledger.jsonl",
        nightly_workflow="nightly.yml",
        record_glob="run-*.json",
        min_tasks=30,
        excluded_sides=("train",),
        published_marker="plain -> memory",
        baseline=improve.Arm("plain", "plain agent"),
        treated=improve.Arm("memory", "with memory"),
        per_try_usd=5.0,
        per_week_usd=60.0,
        validate=(),
    )
    cfg.update(over)
    return improve.Config(**cfg)


@pytest.fixture
def world(tmp_path):
    cfg = make_config(tmp_path)
    cfg.results_dir.mkdir()
    # 35 tasks: 30 fine, 1 fails in both arms, 1 the treatment made worse, 3 pass only when treated.
    outcomes = {f"T-{i}": (True, True) for i in range(101, 131)}
    outcomes["T-40"] = (False, False)
    outcomes["T-19"] = (True, False)
    for t in ("T-06", "T-15", "T-17"):
        outcomes[t] = (False, True)
    for t in outcomes:
        task_file(cfg.tasks_dir, t, first_line=f"Prompt for {t}.")
    write_record(cfg.results_dir, "run-full.json", outcomes)
    return cfg


def run_cli(argv, cfg, *, night=None, validator=None, container=True):
    lines = []
    code = improve.main(
        argv,
        config=cfg,
        nightly=night or nightly(),
        validator=validator or (lambda task_id: improve.Validation(ok=True, detail="")),
        container_running=lambda name: container,
        out=lines.append,
        now=NOW,
    )
    return code, "\n".join(lines)


# ---- the worklist ------------------------------------------------------------------------------


def test_the_worklist_ranks_both_fail_then_treated_worse_then_treated_only(world):
    status = improve.build_status(world, now=NOW, nightly=nightly())
    ids = [i.task_id for i in status.worklist]
    assert (
        ids[0] == "T-40"
        and ids[1] == "T-19"
        and set(ids[2:]) == {"T-06", "T-15", "T-17"}
    )
    assert [i.kind for i in status.worklist[:2]] == ["both_fail", "treated_worse"]
    assert {i.kind for i in status.worklist[2:]} == {"treated_only"}


def test_the_scoreboard_counts_each_arm(world):
    s = improve.build_status(world, now=NOW, nightly=nightly())
    assert (s.tasks, s.baseline_passed, s.treated_passed) == (35, 31, 33)


def test_a_small_run_is_not_a_full_holdout(world):
    write_record(
        world.results_dir,
        "run-spot.json",
        {f"T-0{i}": (True, True) for i in range(1, 5)},
        measured_at="2026-10-01T00:00:00Z",
    )
    s = improve.build_status(world, now=NOW, nightly=nightly())
    assert s.tasks == 35 and s.measured_at.startswith("2026-09-19")


def test_an_excluded_side_is_never_the_reported_run(world):
    write_record(
        world.results_dir,
        "run-train.json",
        {f"T-{i}": (False, False) for i in range(1, 40)},
        measured_at="2026-10-05T00:00:00Z",
        side="train",
    )
    s = improve.build_status(world, now=NOW, nightly=nightly())
    assert s.measured_at.startswith("2026-09-19")


def test_the_newest_full_run_wins(world):
    write_record(
        world.results_dir,
        "run-newer.json",
        {f"T-{i}": (True, True) for i in range(1, 36)},
        measured_at="2026-10-08T00:00:00Z",
    )
    s = improve.build_status(world, now=NOW, nightly=nightly())
    assert s.measured_at.startswith("2026-10-08") and s.worklist == []


def test_a_record_with_other_arms_does_not_count(world):
    # The project names its arms; a record that has different ones is some other experiment.
    write_record(
        world.results_dir,
        "run-other.json",
        {f"T-{i}": (True, True) for i in range(1, 36)},
        measured_at="2026-10-09T00:00:00Z",
        baseline="a",
        treated="b",
    )
    s = improve.build_status(world, now=NOW, nightly=nightly())
    assert s.measured_at.startswith("2026-09-19")


def test_no_results_says_so_instead_of_crashing(tmp_path):
    cfg = make_config(tmp_path)
    cfg.results_dir.mkdir()
    code, text = run_cli(["status"], cfg)
    assert code == 0 and "no full holdout run" in text.lower()


# ---- the adapter -------------------------------------------------------------------------------


def test_the_adapter_file_round_trips_into_a_config(tmp_path):
    toml = textwrap.dedent("""
        [project]
        name = "demo"
        results_dir = "out"
        tasks_dir = "cases"
        ledger = ".improve/ledger.jsonl"
        [nightly]
        workflow = "nightly.yml"
        [holdout]
        record_glob = "run-*.json"
        min_tasks = 12
        excluded_sides = ["train", "dev"]
        published_marker = "a -> b"
        transcripts_glob = "x/{task}__*"
        [environment]
        probe = ["probe", "{name}"]
        [holdout.baseline]
        arm = "a"
        label = "plain"
        [holdout.treated]
        arm = "b"
        label = "improved"
        [budget]
        per_try_usd = 2.5
        per_week_usd = 30
        [[validate]]
        tasks = ["X-1"]
        command = ["check", "{task}"]
        container = "box"
        start_hint = "start box"
        [validate.env]
        K = "v"
        [[validate]]
        command = ["check-all", "{task}"]
    """)
    path = tmp_path / ".improve" / "project.toml"
    path.parent.mkdir()
    path.write_text(toml)
    cfg = improve.load_config(path)
    assert cfg.root == tmp_path and cfg.name == "demo"
    assert cfg.results_dir == tmp_path / "out" and cfg.tasks_dir == tmp_path / "cases"
    assert cfg.ledger == tmp_path / ".improve" / "ledger.jsonl"
    assert cfg.nightly_workflow == "nightly.yml" and cfg.min_tasks == 12
    assert cfg.excluded_sides == ("train", "dev") and cfg.published_marker == "a -> b"
    assert cfg.transcripts_glob == "x/{task}__*" and cfg.probe == ("probe", "{name}")
    assert (cfg.baseline.arm, cfg.baseline.label) == ("a", "plain")
    assert (cfg.treated.arm, cfg.treated.label) == ("b", "improved")
    assert (cfg.per_try_usd, cfg.per_week_usd) == (2.5, 30.0)
    first, default = cfg.validate
    assert first.tasks == ("X-1",) and first.command == ("check", "{task}")
    assert (
        first.container == "box"
        and first.start_hint == "start box"
        and first.env == {"K": "v"}
    )
    assert default.tasks is None and default.container is None


def test_a_misspelt_key_is_an_error_not_a_silent_default(tmp_path):
    path = tmp_path / ".improve" / "project.toml"
    path.parent.mkdir()
    path.write_text(
        '[project]\nname="x"\nresults_dir="r"\ntasks_dir="t"\nledger="l"\nresult_dir="typo"\n'
        '[nightly]\nworkflow="w"\n'
    )
    with pytest.raises(improve.ConfigError, match="result_dir"):
        improve.load_config(path)


def test_a_missing_adapter_says_where_to_put_one(tmp_path):
    with pytest.raises(improve.ConfigError, match="project.toml"):
        improve.load_config(tmp_path / ".improve" / "project.toml")


def test_this_projects_own_adapter_loads(tmp_path):
    repo_adapter = Path(__file__).resolve().parents[1] / "project.toml"
    cfg = improve.load_config(repo_adapter)
    assert cfg.name == "iris-agentic-dev" and cfg.baseline.arm == "tools"
    assert cfg.treated.arm == "tools+skills" and cfg.validate, (
        "it declares how to check a task"
    )
    assert cfg.validate[-1].tasks is None, "the last rule is the default"


def test_the_first_matching_validate_rule_wins(world):
    rules = (
        improve.ValidateRule(
            tasks=("T-40",),
            command=("special", "{task}"),
            container="box-a",
            env={},
            start_hint="",
        ),
        improve.ValidateRule(
            tasks=None,
            command=("default", "{task}"),
            container="box-b",
            env={},
            start_hint="",
        ),
    )
    cfg = make_config(world.root, validate=rules)
    assert improve.rule_for(cfg, "T-40").command == ("special", "{task}")
    assert improve.rule_for(cfg, "T-19").command == ("default", "{task}")


def test_the_arm_labels_in_the_output_come_from_the_adapter(world):
    code, text = run_cli(["status"], world)
    assert "plain agent 31/35" in text and "with memory 33/35" in text
    assert "tools alone" not in text and "with skills" not in text


# ---- spend -------------------------------------------------------------------------------------


def test_spend_is_not_tracked_until_there_is_a_ledger(world):
    code, text = run_cli(["status"], world)
    assert code == 0 and "not tracked yet" in text


def test_spend_is_this_months_ledger_total(world):
    world.ledger.write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"ts": "2026-10-03T10:00:00Z", "cost_usd": 4.25, "what": "try T-40"},
                {"ts": "2026-10-09T10:00:00Z", "cost_usd": 1.0, "what": "try T-19"},
                {"ts": "2026-09-28T10:00:00Z", "cost_usd": 60.0, "what": "last month"},
            ]
        )
        + "\n"
    )
    code, text = run_cli(["status"], world)
    assert "$5.25" in text


# ---- what status prints ------------------------------------------------------------------------


def test_status_is_plain_english_with_the_worklist_in_order(world):
    code, text = run_cli(["status"], world)
    assert code == 0
    assert "Nightly canary" in text and "green" in text and "2026-10-10" in text
    assert text.index("T-40") < text.index("T-19")
    assert "fails in both arms" in text and "treatment made it worse" in text
    assert "improve next" in text


@pytest.mark.parametrize(
    "state,word", [("green", "green"), ("red", "RED"), ("unknown", "unknown")]
)
def test_the_nightly_state_is_stated_not_hidden(world, state, word):
    code, text = run_cli(["status"], world, night=nightly(state))
    assert word in text.split("Nightly canary")[1].split("\n")[0]


def test_a_red_nightly_comes_before_any_task_work(world):
    code, text = run_cli(["status"], world, night=nightly("red"))
    assert "fix the nightly first" in text.lower()


def test_status_json_is_machine_readable(world):
    code, text = run_cli(["status", "--json"], world)
    data = json.loads(text)
    assert data["nightly"]["state"] == "green" and data["tasks"] == 35
    assert data["worklist"][0]["task_id"] == "T-40"
    assert data["budget"] == {"per_try_usd": 5.0, "per_week_usd": 60.0}


# ---- next --------------------------------------------------------------------------------------


def test_next_takes_the_top_item_and_checks_the_task_first(world):
    seen = []
    code, text = run_cli(
        ["next"],
        world,
        validator=lambda t: (seen.append(t), improve.Validation(ok=True, detail=""))[1],
    )
    assert code == 0 and seen == ["T-40"]
    assert (
        "T-40" in text
        and "task is sound" in text.lower()
        and "Prompt for T-40." in text
    )


def test_a_broken_task_is_reported_as_the_problem_not_the_agent(world):
    code, text = run_cli(
        ["next"],
        world,
        validator=lambda t: improve.Validation(
            ok=False, detail="reference did not pass"
        ),
    )
    assert (
        code == 1
        and "task is broken" in text.lower()
        and "reference did not pass" in text
    )
    assert "before blaming the agent" in text.lower()


def test_next_can_be_pointed_at_a_task(world):
    seen = []
    run_cli(
        ["next", "T-19"],
        world,
        validator=lambda t: (seen.append(t), improve.Validation(ok=True, detail=""))[1],
    )
    assert seen == ["T-19"]


def test_an_unknown_task_is_a_clear_error(world):
    code, text = run_cli(["next", "T-999"], world)
    assert code == 2 and "T-999" in text and "not in the last holdout" in text.lower()


def test_next_with_an_empty_worklist_says_so(world):
    write_record(
        world.results_dir,
        "run-clean.json",
        {f"T-{i}": (True, True) for i in range(1, 36)},
        measured_at="2026-10-08T00:00:00Z",
    )
    code, text = run_cli(["next"], world)
    assert code == 0 and "nothing is failing" in text.lower()


def test_next_says_how_to_start_the_container_when_it_is_down(world):
    rule = improve.ValidateRule(
        tasks=None,
        command=("check", "{task}"),
        container="box",
        env={},
        start_hint="docker start box",
    )
    cfg = make_config(world.root, validate=(rule,))
    code, text = run_cli(["next"], cfg, container=False)
    assert code == 3 and "docker start box" in text


def test_a_rule_with_no_container_never_asks_about_one(world):
    rule = improve.ValidateRule(
        tasks=None, command=("check", "{task}"), container=None, env={}, start_hint=""
    )
    cfg = make_config(world.root, validate=(rule,))
    code, text = run_cli(["next"], cfg, container=False)
    assert code == 0 and "task is sound" in text.lower()


def test_a_validated_task_is_not_validated_again_until_its_file_changes(world):
    calls = []
    v = lambda t: (calls.append(t), improve.Validation(ok=True, detail=""))[1]
    run_cli(["next"], world, validator=v)
    run_cli(["next"], world, validator=v)
    assert calls == ["T-40"], "the second call used the cache"
    (world.tasks_dir / "all" / "T-40.yaml").write_text(
        "id: T-40\nprompt: |\n  Changed.\n"
    )
    run_cli(["next"], world, validator=v)
    assert calls == ["T-40", "T-40"], "an edited task is checked again"


def test_next_says_when_there_are_no_transcripts_to_read(world):
    code, text = run_cli(["next"], world)
    assert "no transcript" in text.lower() and "improve try" in text


# ---- free means free, and the engine stays generic ---------------------------------------------


def test_status_and_next_never_start_a_process_of_their_own(world, monkeypatch):
    import subprocess

    def boom(*a, **k):
        raise AssertionError(f"improve status/next ran a process: {a}")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    assert run_cli(["status"], world)[0] == 0
    assert run_cli(["next"], world)[0] == 0


def test_the_engine_names_nothing_about_this_project():
    """The engine must run unchanged in any project, so it may not mention this one. Everything
    project-specific lives in project.toml, which is the only file a new project rewrites."""
    source = (Path(improve.__file__)).read_text().lower()
    for word in (
        "iris",
        "opencode",
        "ladder",
        "docker",
        "skill",
        "tools+",
        "intersystems",
        "corpus",
    ):
        assert word not in source, (
            f"the engine mentions {word!r}; move it to project.toml"
        )


def test_the_engine_imports_nothing_that_spends_money():
    source = Path(improve.__file__).read_text()
    for forbidden in ("driver", "scorer", "billing", "anthropic", "openai"):
        assert forbidden not in source.lower(), (
            f"improve imports or mentions {forbidden}"
        )
