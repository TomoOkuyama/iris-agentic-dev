"""`improve measure` and `improve skills` — 135 T006, written before the code.

`measure` runs the harness for one skill (all its held-out tasks, or its train tasks), and writes a
`measure` event to the ledger: the run file it produced, the measured cost, the commit, and the sha256
of the criteria file the run was taken under. `skills` runs the adapter's verdict command. The engine
knows neither what a skill is nor what the criteria say.

A fake runner stands in for the harness, so no test starts a session.
"""

import hashlib
import json
from pathlib import Path

import pytest

import improve
from test_improve import NOW, make_config, nightly

DRY = "--dry-run"


class Runner:
    def __init__(self, costs=(1.0,), returncode=0, runs_file="results/ladder-1.runs.jsonl", abort_line=False):
        self.costs, self.returncode, self.runs_file, self.abort_line = costs, returncode, runs_file, abort_line
        self.calls = []

    def __call__(self, argv, env, timeout, live=False):
        self.calls.append(list(argv))
        if DRY in argv:
            return improve.RunResult(0, "Ladder estimate: 30 sessions, ~$2.55")
        lines = [f"SKILL-31 tools PASS 9 calls 31.0s ${c:.2f}" for c in self.costs]
        if self.abort_line:
            lines.append("sessions so far: " + self.runs_file)
        else:
            lines.append("sessions written incrementally to " + self.runs_file)
        return improve.RunResult(self.returncode, "\n".join(lines))


def rule(**over):
    base = dict(
        command=(
            "ladder",
            "--subject",
            "{subject}",
            "--side",
            "{side}",
            "--repeats",
            "{repeats}",
            "--cap",
            "{cap}",
            "--spent",
            "{spent}",
        ),
        dry_run_flag=DRY,
        repeats=3,
        cost_regex=r"s \$(\d+\.\d+)",
        runs_file_regex=r"sessions (?:written incrementally to |so far: )(\S+)",
        env={},
        timeout_seconds=3600,
        estimate_note="Estimates run low. The cap bounds the spend.",
        verdict_args=(),
        subjects=(),
    )
    base.update(over)
    return improve.MeasureRule(**base)


@pytest.fixture
def world(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("the criteria\n")
    cfg = make_config(
        tmp_path,
        measures=(rule(),),
        total_usd=300.0,
        per_subject_usd=60.0,
        per_measure_usd=40.0,
        checkpoint_usd=50.0,
        budget_since="2026-10-11T00:00:00Z",
        criteria=str(criteria),
        per_week_usd=300.0,
    )
    cfg.results_dir.mkdir()
    return cfg


def go(argv, cfg, *, runner=None, answer=True, git=("abc1234def", False), skills_runner=None):
    lines, asked = [], []

    def confirm(prompt):
        asked.append(prompt)
        return answer

    runner = runner or Runner()
    code = improve.main(
        argv,
        config=cfg,
        nightly=nightly(),
        validator=lambda t: improve.Validation(ok=True, detail=""),
        container_running=lambda name: True,
        out=lines.append,
        now=NOW,
        runner=runner,
        confirm=confirm,
        who="tom",
        git_state=lambda: git,
    )
    return code, "\n".join(lines), runner, asked


def ledger(cfg):
    if not cfg.ledger.exists():
        return []
    return [json.loads(l) for l in cfg.ledger.read_text().splitlines() if l.strip()]


def spend_event(ts, cost, **kw):
    return {"ts": ts, "id": "IMP-0099", "event": kw.pop("event", "measure"), "cost_usd": cost, **kw}


# ---- the adapter ------------------------------------------------------------------------------


def test_the_measure_and_skills_tables_load_from_toml(tmp_path):
    (tmp_path / ".improve").mkdir()
    path = tmp_path / ".improve" / "project.toml"
    path.write_text(
        """
[project]
name = "x"
results_dir = "r"
tasks_dir = "t"
ledger = "l.jsonl"
[holdout]
baseline = {arm = "a", label = "A"}
treated = {arm = "b", label = "B"}
[budget]
per_try_usd = 5
per_week_usd = 300
total_usd = 300
per_subject_usd = 60
per_measure_usd = 40
checkpoint_usd = 50
since = "2026-10-11T00:00:00Z"
[evidence]
criteria = "criteria.md"
[report]
command = ["python3", "-m", "verdict"]
[[measure]]
command = ["ladder", "--subject", "{subject}"]
runs_file_regex = "file: (\\\\S+)"
cost_regex = "\\\\$(\\\\d+)"
"""
    )
    cfg = improve.load_config(path)
    assert (cfg.total_usd, cfg.per_subject_usd, cfg.per_measure_usd, cfg.checkpoint_usd) == (300.0, 60.0, 40.0, 50.0)
    assert cfg.budget_since == "2026-10-11T00:00:00Z"
    assert cfg.criteria == str(tmp_path / "criteria.md")
    assert cfg.report_command == ("python3", "-m", "verdict")
    assert cfg.measures[0].command == ("ladder", "--subject", "{subject}")
    assert cfg.per_week_usd == 300.0


def test_an_unknown_key_in_the_new_tables_is_an_error(tmp_path):
    (tmp_path / ".improve").mkdir()
    path = tmp_path / ".improve" / "project.toml"
    path.write_text(
        '[project]\nname="x"\nresults_dir="r"\ntasks_dir="t"\nledger="l"\n'
        '[holdout]\nbaseline={arm="a"}\ntreated={arm="b"}\n[report]\ncommnad=["x"]\n'
    )
    with pytest.raises(improve.ConfigError):
        improve.load_config(path)


def test_this_repos_adapter_loads_with_the_135_budget():
    cfg = improve.load_config(Path(__file__).resolve().parents[1] / "project.toml")
    assert cfg.per_week_usd >= 300.0, "the weekly guard must not be lower than the 135 budget"
    assert cfg.total_usd == 300.0
    assert cfg.per_subject_usd == 60.0
    assert cfg.per_try_usd == 5.0
    assert cfg.checkpoint_usd == 50.0
    assert cfg.measures and cfg.report_command and cfg.criteria.endswith("criteria.md")
    assert cfg.aliases.get("skills") == "report"


# ---- measure: asking, capping, writing -----------------------------------------------------------


def test_measure_shows_the_estimate_and_asks(world):
    code, text, runner, asked = go(["measure", "objectscript-tdd"], world)
    assert len(asked) == 1
    assert "~$2.55" in text
    assert any(DRY in c for c in runner.calls)


def test_a_no_runs_nothing_and_writes_nothing(world):
    code, text, runner, asked = go(["measure", "objectscript-tdd"], world, answer=False)
    assert code == 0 and all(DRY in c for c in runner.calls)
    assert ledger(world) == []


def test_the_command_gets_skill_side_repeats_cap_and_spent(world):
    _, _, runner, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--subject") + 1] == "objectscript-tdd"
    assert real[real.index("--side") + 1] == "holdout"
    assert real[real.index("--repeats") + 1] == "3"
    assert real[real.index("--cap") + 1] == "40.0"
    assert real[real.index("--spent") + 1] == "0.0"


def test_verdict_args_are_added_for_a_verdict_run_and_not_for_a_train_run(world):
    world.measures = (rule(verdict_args=("--require-clean",)),)
    _, _, runner, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    assert "--require-clean" in next(c for c in runner.calls if DRY not in c)
    _, _, runner, _ = go(["measure", "objectscript-tdd", "--purpose", "train", "--yes"], world)
    assert "--require-clean" not in next(c for c in runner.calls if DRY not in c)


def test_a_train_measure_asks_for_the_train_side(world):
    _, _, runner, _ = go(["measure", "objectscript-tdd", "--purpose", "train", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--side") + 1] == "train"


def test_the_cap_is_the_smallest_of_the_measure_skill_and_programme_budgets(world):
    world.ledger.write_text(
        json.dumps(spend_event("2026-10-11T08:00:00Z", 35.0, subject="objectscript-tdd")) + "\n"
    )
    _, text, runner, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "25.0", "$60 for the skill, $35 spent"
    assert "$25.00 left for objectscript-tdd" in text


def test_the_programme_budget_bounds_the_cap_too(world):
    world.ledger.write_text(
        json.dumps(spend_event("2026-10-11T08:00:00Z", 290.0, subject="iris-sql")) + "\n"
    )
    _, _, runner, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "10.0"


def test_spend_before_the_budget_start_does_not_count(world):
    world.ledger.write_text(
        json.dumps(spend_event("2026-09-20T08:00:00Z", 250.0, subject="objectscript-tdd", event="run")) + "\n"
    )
    _, _, runner, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "40.0"


def test_an_exhausted_skill_budget_refuses_before_spending(world):
    world.ledger.write_text(
        json.dumps(spend_event("2026-10-11T08:00:00Z", 60.0, subject="objectscript-tdd")) + "\n"
    )
    code, text, runner, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    assert code == 5
    assert "spent" in text.lower()
    assert all(DRY in c for c in runner.calls) or runner.calls == []


def test_the_measure_event_names_the_run_file_cost_commit_and_criteria_hash(world):
    code, text, runner, _ = go(["measure", "objectscript-tdd", "--yes"], world, runner=Runner(costs=(1.5, 2.0)))
    assert code == 0
    event = ledger(world)[-1]
    assert event["event"] == "measure"
    assert event["subject"] == "objectscript-tdd"
    assert event["side"] == "holdout" and event["purpose"] == "verdict"
    assert event["runs_file"] == "results/ladder-1.runs.jsonl"
    assert event["cost_usd"] == pytest.approx(3.5) and event["sessions"] == 2
    assert event["commit"] == "abc1234def" and event["dirty"] is False
    assert event["criteria_sha256"] == hashlib.sha256(b"the criteria\n").hexdigest()
    assert event["aborted"] is False and event["returncode"] == 0
    assert event["id"].startswith("IMP-")


def test_an_aborted_run_still_records_its_spend_and_run_file(world):
    runner = Runner(costs=(4.0, 4.0), returncode=3, abort_line=True)
    code, text, _, _ = go(["measure", "objectscript-tdd", "--yes"], world, runner=runner)
    event = ledger(world)[-1]
    assert code == 7
    assert event["aborted"] is True and event["cost_usd"] == pytest.approx(8.0)
    assert event["runs_file"] == "results/ladder-1.runs.jsonl"


def test_a_run_that_names_no_run_file_is_recorded_as_aborted(world):
    class Silent(Runner):
        def __call__(self, argv, env, timeout, live=False):
            if DRY in argv:
                return super().__call__(argv, env, timeout, live)
            return improve.RunResult(0, "SKILL-31 tools PASS 9 calls 31.0s $1.00")

    code, _, _, _ = go(["measure", "objectscript-tdd", "--yes"], world, runner=Silent())
    event = ledger(world)[-1]
    assert event["aborted"] is True and event.get("runs_file") is None


def test_a_dirty_tree_is_recorded_on_the_event(world):
    go(["measure", "objectscript-tdd", "--yes"], world, git=("abc", True))
    assert ledger(world)[-1]["dirty"] is True


def test_crossing_a_fifty_dollar_mark_prints_a_checkpoint_and_exits_8(world):
    world.ledger.write_text(
        json.dumps(spend_event("2026-10-11T08:00:00Z", 48.0, subject="iris-sql")) + "\n"
    )
    code, text, _, _ = go(["measure", "objectscript-tdd", "--yes"], world, runner=Runner(costs=(3.0,)))
    assert "CHECKPOINT" in text and "$50" in text
    assert code == 8


def test_staying_under_the_mark_prints_no_checkpoint(world):
    code, text, _, _ = go(["measure", "objectscript-tdd", "--yes"], world, runner=Runner(costs=(3.0,)))
    assert "CHECKPOINT" not in text and code == 0


def test_the_summary_line_gives_run_skill_and_programme_spend(world):
    _, text, _, _ = go(["measure", "objectscript-tdd", "--yes"], world, runner=Runner(costs=(3.0,)))
    assert "$3.00 this run" in text
    assert "$3.00 of $60.00 for objectscript-tdd" in text
    assert "$3.00 of $300.00 overall" in text


# ---- try carries the criteria hash, the total budget and the skill ---------------------------------


def test_a_measure_without_a_measure_rule_is_refused(world):
    world.measures = ()
    code, text, _, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    assert code == 2 and "[[measure]]" in text


# ---- skills ---------------------------------------------------------------------------------------


def test_report_runs_the_adapters_verdict_command_and_prints_it(world):
    world.report_command = ("verdict", "--x")
    runner = Runner()

    class Verdict(Runner):
        def __call__(self, argv, env, timeout, live=False):
            self.calls.append(list(argv))
            return improve.RunResult(0, "objectscript-tdd\n  verdict no verdict")

    runner = Verdict()
    code, text, runner, _ = go(["report"], world, runner=runner)
    assert code == 0 and "no verdict" in text
    call = runner.calls[0]
    assert call[:2] == ["verdict", "--x"]
    assert "--ledger" in call and "--criteria" in call and "--root" in call


def test_report_without_a_command_says_so(world):
    world.report_command = ()
    code, text, _, _ = go(["report"], world)
    assert code == 2 and "[report]" in text


def test_an_adapter_alias_names_a_verb_in_the_projects_own_words(world):
    world.report_command = ("verdict",)
    world.aliases = {"skills": "report"}

    class Verdict(Runner):
        def __call__(self, argv, env, timeout, live=False):
            self.calls.append(list(argv))
            return improve.RunResult(0, "ok")

    code, text, runner, _ = go(["skills"], world, runner=Verdict())
    assert code == 0 and text == "ok"


# ---- try shares the programme budget, the subject tag and the criteria hash ---------------------------


def try_world(world, tmp_path):
    from test_improve import task_file, write_record
    from test_try import try_rule

    world.tries = (try_rule(),)
    outcomes = {f"T-{i}": (True, True) for i in range(101, 131)}
    outcomes["T-40"] = (False, False)
    for t in outcomes:
        task_file(world.tasks_dir, t)
    write_record(world.results_dir, "run-full.json", outcomes)
    return world


def go_try(argv, cfg):
    from test_try import Runner as TryRunner

    lines = []
    runner = TryRunner()
    code = improve.main(
        argv,
        config=cfg,
        nightly=nightly(),
        validator=lambda t: improve.Validation(ok=True, detail=""),
        container_running=lambda name: True,
        out=lines.append,
        now=NOW,
        runner=runner,
        confirm=lambda p: True,
        who="tom",
        git_state=lambda: ("abc1234def", False),
    )
    return code, "\n".join(lines), runner


def test_a_try_run_event_carries_the_criteria_hash_and_the_subject(world, tmp_path):
    try_world(world, tmp_path)
    go_try(["try", "T-40", "--yes", "--subject", "objectscript-tdd"], world)
    run = [e for e in ledger(world) if e["event"] == "run"][-1]
    assert run["criteria_sha256"] == hashlib.sha256(b"the criteria\n").hexdigest()
    assert run["subject"] == "objectscript-tdd"


def test_a_try_is_capped_by_what_is_left_of_the_subjects_budget(world, tmp_path):
    try_world(world, tmp_path)
    world.ledger.write_text(
        json.dumps(spend_event("2026-10-11T08:00:00Z", 58.0, subject="objectscript-tdd")) + "\n"
    )
    _, text, runner = go_try(["try", "T-40", "--yes", "--subject", "objectscript-tdd"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "2.0"


def test_a_try_is_capped_by_what_is_left_overall(world, tmp_path):
    try_world(world, tmp_path)
    world.ledger.write_text(
        json.dumps(spend_event("2026-10-11T08:00:00Z", 299.0, subject="iris-sql")) + "\n"
    )
    _, _, runner = go_try(["try", "T-40", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "1.0"


# ---- a continuation of a run that hit its cap ---------------------------------------------------------


def test_a_continuation_passes_extra_arguments_and_names_the_run_it_continues(world):
    _, _, runner, _ = go(
        ["measure", "objectscript-tdd", "--yes", "--continues", "IMP-0011",
         "--arg=--task", "--arg=SKILL-31", "--arg=--start-repeat", "--arg=2"],
        world,
    )
    real = next(c for c in runner.calls if DRY not in c)
    assert real[-4:] == ["--task", "SKILL-31", "--start-repeat", "2"]
    event = ledger(world)[-1]
    assert event["continues"] == "IMP-0011"


def test_a_plain_measure_has_no_continues_field(world):
    go(["measure", "objectscript-tdd", "--yes"], world)
    assert "continues" not in ledger(world)[-1]


# ---- a rule can name the subjects it is for (another container, another port) ----------------------------


def test_a_measure_rule_that_names_the_subject_wins_over_the_default(world):
    world.measures = (
        rule(subjects=("iris-ai-hub",), command=("ladder", "--subject", "{subject}", "--web-port", "52781")),
        rule(),
    )
    _, _, runner, _ = go(["measure", "iris-ai-hub", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert "--web-port" in real and real[real.index("--web-port") + 1] == "52781"
    _, _, runner2, _ = go(["measure", "objectscript-tdd", "--yes"], world)
    real2 = next(c for c in runner2.calls if DRY not in c)
    assert "--web-port" not in real2


def test_this_repos_adapter_sends_the_ai_hub_skill_to_the_ai_hub_container():
    cfg = improve.load_config(Path(__file__).resolve().parents[1] / "project.toml")
    hub = next(r for r in cfg.measures if "iris-ai-hub" in r.subjects)
    assert hub.command[hub.command.index("--web-port") + 1] == "52781"
    assert hub.command[hub.command.index("--container") + 1] == "iad-aihub-iris"
    default = next(r for r in cfg.measures if not r.subjects)
    assert "--web-port" not in default.command
