//! What `objectscript-navigation` and `objectscript-repair` now say about finding a class's
//! members and checking a rename, run through the binary against live IRIS. The text guards are
//! in `tests/unit/test_skill_symbols_claims.rs`.

use iris_agentic_dev_core::testing::{answer_text, live_env, require_iad_binary, McpSession};

const LIB: &str = "IadSkillSym.Lib";
const CALLER: &str = "IadSkillSym.Caller";

fn write_env() -> Vec<(String, String)> {
    let mut env = live_env();
    env.push(("IRIS_WRITE_TOOLS_ENABLED".into(), "1".into()));
    env.push(("IRIS_DESTRUCTIVE_TOOLS_ENABLED".into(), "1".into()));
    env
}

fn payload(answer: &serde_json::Value) -> serde_json::Value {
    let text = answer
        .pointer("/result/content/0/text")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_else(|| panic!("no text content in {}", answer_text(answer)));
    serde_json::from_str(text).unwrap_or_else(|_| serde_json::json!({ "text": text }))
}

fn put(s: &mut McpSession, name: &str, content: &str) -> serde_json::Value {
    payload(&s.call(
        "iris_doc",
        &serde_json::json!({
            "mode": "put", "name": format!("{name}.cls"), "content": content,
            "compile": true, "namespace": "USER"
        }),
    ))
}

#[test]
#[ignore = "requires live IRIS (iris-dev-iris) and the built binary; writes and deletes IadSkillSym.*"]
fn symbols_names_classes_introspect_lists_members_and_a_renamed_call_still_compiles() {
    let Some(_bin) = require_iad_binary() else {
        return;
    };
    let mut s = McpSession::start(&write_env());
    let lib = put(
        &mut s,
        LIB,
        &format!("Class {LIB} Extends %RegisteredObject\n{{\n\nClassMethod Fresh() As %Integer\n{{\n    Quit 1\n}}\n\n}}\n"),
    );
    // The caller still uses the method's old name, as a missed call site after a rename would.
    let caller = put(
        &mut s,
        CALLER,
        &format!("Class {CALLER} Extends %RegisteredObject\n{{\n\nClassMethod Run() As %Integer\n{{\n    Quit ##class({LIB}).Stale()\n}}\n\n}}\n"),
    );
    let ran = answer_text(&s.call(
        "iris_execute",
        &serde_json::json!({ "code": format!("Write ##class({CALLER}).Run()"), "namespace": "USER" }),
    ));
    let classes = payload(&s.call(
        "iris_symbols",
        &serde_json::json!({ "query": "IadSkillSym.*", "namespace": "USER" }),
    ));
    let members_by_symbols = payload(&s.call(
        "iris_symbols",
        &serde_json::json!({ "query": format!("{LIB}.*"), "namespace": "USER" }),
    ));
    let introspected = payload(&s.call(
        "docs_introspect",
        &serde_json::json!({ "class_name": LIB, "namespace": "USER" }),
    ));
    for name in [LIB, CALLER] {
        s.call(
            "iris_doc",
            &serde_json::json!({ "mode": "delete", "name": format!("{name}.cls"), "namespace": "USER" }),
        );
    }

    assert_eq!(lib["success"], true, "put {LIB}: {lib}");
    // A call to a method that does not exist compiles: the compiler does not check a rename.
    assert_eq!(caller["success"], true, "put {CALLER}: {caller}");
    assert!(
        ran.contains("METHOD DOES NOT EXIST"),
        "only running it fails: {ran}"
    );

    let names: Vec<String> = classes["symbols"]
        .as_array()
        .map(|a| a.iter().map(|s| s.to_string()).collect())
        .unwrap_or_default();
    assert!(
        names.iter().any(|n| n.contains(LIB)) && names.iter().any(|n| n.contains(CALLER)),
        "Pkg.* lists the package's classes: {classes}"
    );
    assert!(
        !classes.to_string().contains("Fresh"),
        "no members: {classes}"
    );
    assert_eq!(
        members_by_symbols["count"], 0,
        "Pkg.Class.* finds nothing: {members_by_symbols}"
    );
    assert!(
        introspected.to_string().contains("\"Fresh\""),
        "docs_introspect lists the members: {introspected}"
    );
}
