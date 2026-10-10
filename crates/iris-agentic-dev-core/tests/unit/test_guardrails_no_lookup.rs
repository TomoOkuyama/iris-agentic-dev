//! The guardrails skill told the agent to pass a checklist before showing code, and the sessions that
//! loaded it then searched the docs and the web for items the checklist already settles (status
//! propagation, transactions). Thirteen paired sessions on the six guardrails tasks: 4.7 doc searches
//! against 1.1, 3.5 web fetches against 1.5, 30 calls against 19, the same passes. The skill now says
//! the list is settled. This guard keeps that sentence near the top and keeps the file from growing
//! past its size after the edit, because every byte rides in the context of every later step.

use std::path::PathBuf;

fn guardrails() -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../skills/skills/objectscript-guardrails/SKILL.md");
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

#[test]
fn the_checklist_says_it_is_settled_and_not_to_look_it_up() {
    let t = guardrails();
    let top: String = t
        .split("# ObjectScript — Hard Gate")
        .nth(1)
        .expect("the H1 is there")
        .chars()
        .take(900)
        .collect();
    let lower = top.to_lowercase();
    assert!(
        lower.contains("do not search the docs or the web"),
        "the opening must tell the agent not to look listed items up: {top}"
    );
    assert!(
        lower.contains("settled") || lower.contains("already checked"),
        "and say why: {top}"
    );
}

#[test]
fn the_gate_still_gates() {
    let t = guardrails();
    assert!(
        t.contains("Do not show ObjectScript code until this checklist passes"),
        "the edit changes how the list is applied, not whether"
    );
}

#[test]
fn the_skill_does_not_grow_past_its_size_after_this_edit() {
    let bytes = guardrails().len();
    assert!(
        bytes <= 6700,
        "guardrails is {bytes} bytes; it was 6,361 before this edit, which may add one sentence"
    );
}
