//! 136: `ensemble-production` teaches the kinds of class the Portal's BPL, DTL and Rule editors open,
//! and says so before it teaches code-based processes. Each fact here is measured live in
//! `tests/integration/test_interop_ui_136_live.rs`.

use std::path::PathBuf;

fn skill() -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../skills/skills/ensemble-production/SKILL.md");
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display()))
}

fn section(t: &str) -> &str {
    let start = t
        .find("## Write what the editors can open")
        .expect("the skill must have a section named 'Write what the editors can open'");
    let rest = &t[start + 3..];
    let end = rest.find("\n## ").map(|i| i + 3).unwrap_or(rest.len());
    &t[start..start + end]
}

#[test]
fn the_editor_section_comes_before_the_code_based_gotchas() {
    let t = skill();
    let editors = t
        .find("## Write what the editors can open")
        .expect("section");
    let code = t
        .find("## Code-based processes")
        .expect("the OnRequest gotchas must sit under 'Code-based processes'");
    assert!(editors < code, "the editor section must come first");
    assert!(
        t[code..].contains("OnRequest signature"),
        "the OnRequest signature gotcha moved under 'Code-based processes'"
    );
}

#[test]
fn the_section_names_each_editor_kind() {
    let t = skill();
    let s = section(&t);
    for needle in [
        "Ens.BusinessProcessBPL",
        "XData BPL",
        "Ens.DataTransformDTL",
        "XData DTL",
        "Ens.Rule.Definition",
        "XData RuleDefinition",
        "Ens.Rule.GeneralBusinessRuleAssist",
        "EnsLib.MsgRouter.RuleAssist",
        "is not a BPL business process",
    ] {
        assert!(s.contains(needle), "the section must name {needle:?}");
    }
}

#[test]
fn the_section_states_the_measured_rules() {
    let t = skill();
    let s = section(&t);
    for (needle, why) in [
        ("Ens.Rule.FunctionSet", "lookups go in rule functions"),
        ("bare name", "a function is called by its bare name"),
        ("read-only", "the Rule Editor's Test button runs functions"),
        ("resultLocation", "the rule's return value"),
        ("reasonLocation", "which rules fired"),
        ("rule#1(", "the reason format"),
        ("async=\"0\"", "a synchronous call"),
        ("timeout", "the call's timeout"),
        ("<scope>", "a failed call ends the process unless caught"),
        ("<catchall>", "the fault handler"),
        ("asks for", "code-based classes only on request"),
    ] {
        assert!(
            s.contains(needle),
            "{why}: the section must contain {needle:?}"
        );
    }
    assert!(
        !s.contains("##class(") || !s.contains("condition=\"##class("),
        "a rule condition must not call a function with ##class(...)"
    );
}

#[test]
fn the_skill_stays_under_its_cap() {
    let n = skill().len();
    assert!(
        n <= 30_000,
        "ensemble-production is {n} bytes; the cap is 30000"
    );
}

/// US3: pyprod keeps its Python path, and the skill says what a Portal edit does to it. Measured on a
/// throwaway container (research-docs.md F11).
#[test]
fn the_python_path_states_the_round_trip_limit() {
    let t = skill();
    let start = t
        .find("**Rules for declarative definitions:**")
        .expect("declarative rules");
    let rules = &t[start..start + t[start..].find("\n---").expect("end of the rules")];
    for needle in ["source of truth", "overwritten the next time", "BPL Editor"] {
        assert!(rules.contains(needle), "the pyprod rules must contain {needle:?}");
    }
}

/// 138 research: `Ens.Director` has no `SendRequestSync`. The verified route to a process from a
/// script is an adapterless service's `SendRequestSync` (interop_ui_136_facts_the_skill_states).
#[test]
fn the_skill_does_not_teach_a_method_ens_director_lacks() {
    let t = skill();
    assert!(
        !t.contains("##class(Ens.Director).SendRequestSync"),
        "Ens.Director has no SendRequestSync"
    );
    assert!(
        t.contains("svc.SendRequestSync("),
        "the testing section must show the adapterless service's SendRequestSync"
    );
}
