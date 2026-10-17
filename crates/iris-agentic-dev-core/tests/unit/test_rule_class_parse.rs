//! iris_business_rule_info reads rule classes (Ens.Rule.Definition with XData RuleDefinition), the
//! kind the Rule Editor opens. Before this, it read only the legacy Ens.Rule.RuleSet table and
//! answered RULE_NOT_FOUND for every rule written since 2012.
//!
//! The ObjectScript side writes one line per element, free text last so a `|` inside a condition
//! survives. These tests pin the parsers on that format.

use iris_agentic_dev_core::tools::interop::{parse_rule_class_get, parse_rule_class_list};

#[test]
fn list_lines_become_class_rules() {
    let raw = "CLS|Ens.Rule.GeneralBusinessRuleAssist|2026-10-17 10:00:00|Bench.Intake.Rules|Decide the intake outcome\n\
               CLS||2026-10-16 09:00:00|Bench.Other.Rule|\n\
               DONE\n";
    let rules = parse_rule_class_list(raw);
    assert_eq!(rules.len(), 2);
    assert_eq!(rules[0]["name"], "Bench.Intake.Rules");
    assert_eq!(rules[0]["class_name"], "Bench.Intake.Rules");
    assert_eq!(rules[0]["kind"], "class");
    assert_eq!(rules[0]["rule_type"], "Ens.Rule.GeneralBusinessRuleAssist");
    assert_eq!(rules[0]["description"], "Decide the intake outcome");
    assert_eq!(rules[0]["modified"], "2026-10-17 10:00:00");
    // A rule class with no RuleAssistClass still opens in the editor, as "(unknown)".
    assert_eq!(rules[1]["rule_type"], serde_json::Value::Null);
}

#[test]
fn list_ignores_lines_it_does_not_know() {
    assert!(parse_rule_class_list("noise\nDONE\n").is_empty());
}

#[test]
fn get_builds_the_tree_and_the_flat_lists() {
    let raw = "DEF|Ens.Rule.GeneralBusinessRuleAssist|general|Bench.Intake.Context|Intake rules\n\
               SET|1|||main\n\
               RULE|1|0|duplicate\n\
               WHEN|Bench.Intake.Fn.IsDuplicate(Case.Id)||(Case.Type=\"other\")\n\
               ACT|W|assign|Reasons|||Reasons_\"duplicate;\"\n\
               ACT|W|return||||\"invalid\"\n\
               RULE|1|1|card\n\
               WHEN|Case.Type=\"id_card\"\n\
               ACT|W|return||||\"routine\"\n\
               ACT|O|return||||\"further_review\"\n\
               ACT|S|return||||\"further_review\"\n\
               DONE\n";
    let v = parse_rule_class_get(raw).expect("parses");
    assert_eq!(v["kind"], "class");
    assert_eq!(v["rule_type"], "Ens.Rule.GeneralBusinessRuleAssist");
    assert_eq!(v["context"], "Bench.Intake.Context");
    assert_eq!(v["description"], "Intake rules");

    let set = &v["rule_sets"][0];
    assert_eq!(set["name"], "main");
    let dup = &set["rules"][0];
    assert_eq!(dup["name"], "duplicate");
    assert_eq!(dup["disabled"], false);
    // The `||` inside the condition is part of the condition, not a field separator.
    assert_eq!(
        dup["whens"][0]["condition"],
        "Bench.Intake.Fn.IsDuplicate(Case.Id)||(Case.Type=\"other\")"
    );
    assert_eq!(dup["whens"][0]["actions"][0]["type"], "assign");
    assert_eq!(dup["whens"][0]["actions"][0]["property"], "Reasons");
    assert_eq!(dup["whens"][0]["actions"][1]["value"], "\"invalid\"");
    assert_eq!(set["rules"][1]["disabled"], true);
    assert_eq!(
        set["rules"][1]["otherwise"][0]["value"],
        "\"further_review\""
    );
    assert_eq!(set["actions"][0]["type"], "return");

    // The flat lists keep the old response shape usable: one entry per condition and action.
    assert_eq!(v["conditions"].as_array().unwrap().len(), 2);
    assert_eq!(v["conditions"][1]["rule"], "card");
    assert_eq!(v["actions"].as_array().unwrap().len(), 5);
}

#[test]
fn get_reports_the_load_error() {
    let err = parse_rule_class_get("ERROR|XDATA block 'RuleDefinition' is not defined\n")
        .expect_err("an error line is an error");
    assert!(err.contains("RuleDefinition"), "{err}");
}

#[test]
fn get_without_a_def_line_is_an_error() {
    assert!(parse_rule_class_get("DONE\n").is_err());
}
