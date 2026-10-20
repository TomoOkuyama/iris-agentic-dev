//! The iris-ai-hub skill let the agent keep searching an index that has no AI Hub pages. On the
//! 2026-09-30 ladder (SKILL-24 and SKILL-25, three repeats, tools+skill arm) the six sessions made
//! 110 `iris_doc_search` calls and every one returned zero hits; one SKILL-25 session made 53 and
//! cost $1.65, while the session that made none cost $0.24. The tools-only arm made 13 such calls,
//! all empty. The skill now says to stop after two empty results and read the installed class or the
//! doc file. This guard keeps that rule and holds the file to its size before the edit, because every
//! byte rides in the context of every later step.

use std::path::PathBuf;

fn skill() -> String {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../skills/skills/iris-ai-hub/SKILL.md");
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

#[test]
fn the_skill_says_to_stop_searching_an_index_that_returns_nothing() {
    let t = skill();
    let s = t
        .split("\n## Search the source, not the index\n")
        .nth(1)
        .expect("the skill has a section on searching")
        .split("\n## ")
        .next()
        .unwrap()
        .to_lowercase();
    assert!(s.contains("iris_doc_search"), "{s}");
    assert!(s.contains("zero hits"), "says what was seen: {s}");
    assert!(
        s.contains("after two empty results"),
        "gives the stop rule: {s}"
    );
    assert!(
        s.contains("docs_introspect") && s.contains("mode: \"get\""),
        "and where to look instead: {s}"
    );
}

#[test]
fn the_skill_does_not_grow_past_its_size_before_this_edit() {
    let bytes = skill().len();
    assert!(
        bytes <= 13153,
        "iris-ai-hub is {bytes} bytes; it was 13,153 before this edit"
    );
}
