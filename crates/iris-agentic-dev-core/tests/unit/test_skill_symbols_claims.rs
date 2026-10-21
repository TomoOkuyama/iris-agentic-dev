//! `objectscript-navigation` and `objectscript-repair` said `iris_symbols(query="ClassName.*")`
//! lists a class's members. It matches class names only: `Pkg.*` lists the classes in a package,
//! and `Pkg.Class.*` returns nothing. The members come from `docs_introspect`. The facts are
//! measured live in `tests/integration/test_skill_symbols_live.rs`.

use std::path::PathBuf;

fn skill(name: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join(format!("../../skills/skills/{name}/SKILL.md"));
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display()))
}

#[test]
fn no_skill_says_iris_symbols_lists_members() {
    for name in ["objectscript-navigation", "objectscript-repair"] {
        let text = skill(name);
        for line in text.lines() {
            let l = line.to_ascii_lowercase();
            assert!(
                !(l.contains("iris_symbols") && l.contains("member")),
                "{name}: iris_symbols does not list members: {line}"
            );
        }
    }
}

#[test]
fn both_skills_send_member_lookups_to_docs_introspect() {
    for name in ["objectscript-navigation", "objectscript-repair"] {
        assert!(
            skill(name).contains("docs_introspect(class_name="),
            "{name} must name docs_introspect for a class's members"
        );
    }
}

/// A rename is not checked by compiling: a call to the old name compiles.
#[test]
fn the_repair_skill_does_not_trust_the_compiler_with_a_rename() {
    let t = skill("objectscript-repair");
    assert!(
        t.contains("METHOD DOES NOT EXIST"),
        "say how a missed call site fails"
    );
    assert!(
        t.contains("iris_search"),
        "name the tool that finds the old name"
    );
}
