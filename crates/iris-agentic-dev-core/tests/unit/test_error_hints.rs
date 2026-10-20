//! Specs 125 and 129: an IRIS error that matches a rule carries a `hint` and a `hint_ref`;
//! anything else carries neither.
//!
//! Every input string below is copied from a live run on iris-dev-iris (spec 125 research R1, R2;
//! spec 129 research R1–R6), not written from memory of what IRIS says.

use iris_agentic_dev_core::tools::error_hints::{
    cited_sections, coding_pack_from, coding_pack_on, compile_error_hint, compiled_source_hint,
    execute_method_hint, matcher_ids, rules, runtime_error_hint, sql_error_hint, Hint,
    KNOWN_CALLBACKS,
};
use iris_agentic_dev_core::tools::{IrisTools, Toolset};
use std::path::Path;

const SQL_12_INSERT: &str = "ERROR #5540: SQLCODE: -12 Message:  A term expected, beginning with \
either of:  identifier, constant, aggregate, $$, (, :, +, -, %ALPHAUP, %EXACT, %MVR %SQLSTRING, \
%SQLUPPER, %STRING, %TRUNCATE, or %UPPER^ INSERT INTO DemoB . Todo ( Title , Completed ) VALUES ( $";

const SQL_12_SELECT: &str = "ERROR #5540: SQLCODE: -12 Message:  A term expected, beginning with \
either of:  identifier, constant, aggregate, $$, (, :, +, -, %ALPHAUP, %EXACT, %MVR %SQLSTRING, \
%SQLUPPER, %STRING, %TRUNCATE, or %UPPER^ SELECT $";

fn table_missing(name: &str) -> String {
    format!("ERROR #5540: SQLCODE: -30 Message:  Table '{name}' not found")
}

fn class_missing(class: &str) -> String {
    format!(
        "ERROR: <CLASS DOES NOT EXIST> 150 Execute+11^IrisDevTmp.IrisDevRun22527a5816fd.1 {class}"
    )
}

fn sql(msg: &str, query: &str) -> Option<Hint> {
    sql_error_hint(msg, query, "USER")
}

fn rule_of(h: &Option<Hint>) -> Option<&str> {
    h.as_ref().map(|h| h.rule())
}

// ── sql_objectscript_function (spec 125, wording fixed in 129) ──────────────────────────────

#[test]
fn sqlcode_12_at_a_dollar_points_at_current_timestamp() {
    for msg in [SQL_12_INSERT, SQL_12_SELECT] {
        let h = sql(msg, "SELECT $ZDATE(1)").expect("SQLCODE -12 at `$` has a rule");
        assert_eq!(h.rule(), "sql_objectscript_function");
        assert!(h.text().contains("CURRENT_TIMESTAMP"), "{}", h.text());
        assert_eq!(h.skill(), "objectscript-sql-patterns");
    }
}

/// Research R1: `$HOROLOG` works in IRIS SQL, so the hint must not name it as the culprit.
#[test]
fn sqlcode_12_hint_does_not_blame_horolog() {
    let h = sql(SQL_12_SELECT, "").unwrap();
    assert!(
        !h.text().contains("such as $ZDATETIME or $HOROLOG"),
        "{}",
        h.text()
    );
}

#[test]
fn sqlcode_12_elsewhere_gets_no_hint() {
    let msg = SQL_12_SELECT.replace("^ SELECT $", "^ SELECT FROM");
    assert!(sql(&msg, "SELECT FROM Test129.Hint").is_none());
}

#[test]
fn a_double_dollar_at_the_marker_is_not_the_objectscript_rule() {
    let msg = SQL_12_SELECT.replace("^ SELECT $", "^ SELECT $$");
    assert!(sql(&msg, "").is_none());
}

#[test]
fn unmatched_sqlcodes_get_no_hint() {
    let msg = "ERROR #5540: SQLCODE: -30 Message:  Table 'SQLUSER.NOPE' not found^ SELECT $";
    assert!(sql(msg, "SELECT * FROM Nope").is_none());
    let msg = "ERROR #5540: SQLCODE: -51 Message:  An SQL statement expected, WRITE found^ WRITE";
    assert!(sql(msg, "WRITE 1").is_none());
}

// ── sys_only_table (research R2) ─────────────────────────────────────────────────────────────

#[test]
fn a_security_or_config_table_outside_sys_points_at_sys() {
    for (reported, query) in [
        ("SECURITY.USERS", "SELECT TOP 1 Name FROM Security.Users"),
        ("SECURITY.ROLES", "SELECT TOP 1 Name FROM Security.Roles"),
        ("CONFIG.NAMESPACES", "Config.Namespaces"),
    ] {
        let h = sql(&table_missing(reported), query)
            .unwrap_or_else(|| panic!("{reported} in USER has a rule"));
        assert_eq!(h.rule(), "sys_only_table");
        assert!(h.text().contains("\"%SYS\""), "{}", h.text());
        // The query's own spelling, not IRIS's upper-cased one.
        let spelled = query.split_whitespace().last().unwrap();
        assert!(h.text().contains(spelled), "{}", h.text());
        assert_eq!(h.skill(), "iris-agentic-dev");
    }
}

#[test]
fn sys_only_table_needs_a_namespace_other_than_sys_and_skips_sys_schema() {
    let msg = table_missing("SECURITY.NOSUCH");
    assert!(sql_error_hint(&msg, "SELECT * FROM Security.NoSuch", "%SYS").is_none());
    assert!(sql_error_hint(&msg, "SELECT * FROM Security.NoSuch", "%sys").is_none());
    // SYS.Database is a class, not a table, even in %SYS.
    assert!(sql(&table_missing("SYS.DATABASE"), "SELECT * FROM SYS.Database").is_none());
}

#[test]
fn explain_wrapped_errors_are_read_by_their_inner_sqlcode() {
    let msg = "ERROR #5540: SQLCODE: -482 Message: EXPLAIN error: SQLCODE = -30 :  Table \
               'SECURITY.USERS' not found";
    let h = sql(msg, "SELECT Name FROM Security.Users");
    assert_eq!(rule_of(&h), Some("sys_only_table"));
}

// ── deep_package_table (research R3) ─────────────────────────────────────────────────────────

#[test]
fn a_three_level_name_cut_to_two_gets_the_underscore_spelling() {
    let h = sql(
        &table_missing("SUB.DEEP"),
        "SELECT TOP 1 Name FROM Test129.Sub.Deep",
    )
    .expect("rule");
    assert_eq!(h.rule(), "deep_package_table");
    assert!(h.text().contains("Test129_Sub.Deep"), "{}", h.text());
    assert!(h.text().contains("Test129.Sub.Deep"), "{}", h.text());
    assert_eq!(h.skill(), "objectscript-sql-patterns");

    // count mode passes the bare table name as the query.
    let h = sql(&table_missing("SUB.DEEP"), "Test129.Sub.Deep");
    assert_eq!(rule_of(&h), Some("deep_package_table"));

    let h = sql(
        &table_missing("CLASS.DEFINITION"),
        "SELECT Name FROM %Dictionary.Class.Definition",
    )
    .expect("rule");
    assert!(
        h.text().contains("%Dictionary_Class.Definition"),
        "{}",
        h.text()
    );
}

#[test]
fn a_two_level_missing_table_is_not_a_deep_name() {
    assert!(sql(
        &table_missing("NOPE.NOSUCHTABLE"),
        "SELECT * FROM Nope.NoSuchTable"
    )
    .is_none());
}

// ── double_quoted_string (research R4) ───────────────────────────────────────────────────────

const SQL_29_HELLO: &str = "ERROR #5540: SQLCODE: -29 Message:  Field 'HELLO' not found in the \
applicable tables^ SELECT Title FROM Test129 . Hint WHERE Title = \"hello\"";

#[test]
fn a_double_quoted_string_read_as_a_field_gets_single_quotes() {
    let h = sql(
        SQL_29_HELLO,
        "SELECT Title FROM Test129.Hint WHERE Title = \"hello\"",
    )
    .expect("rule");
    assert_eq!(h.rule(), "double_quoted_string");
    assert!(h.text().contains("'hello'"), "{}", h.text());
    assert_eq!(h.skill(), "objectscript-sql-patterns");

    let msg = "ERROR #5540: SQLCODE: -29 Message:  Field '%PERSISTENT' not found in the \
               applicable tables^ SELECT Name FROM %Dictionary . ClassDefinition WHERE Super = \"%Persistent\"";
    let h = sql(
        msg,
        "SELECT Name FROM %Dictionary.ClassDefinition WHERE Super = \"%Persistent\"",
    );
    assert_eq!(rule_of(&h), Some("double_quoted_string"));
}

/// Replay item neg-quoted-missing-field: a quoted identifier in the select list is not a string.
#[test]
fn a_quoted_missing_column_is_not_a_string_literal() {
    let msg = "ERROR #5540: SQLCODE: -29 Message:  Field 'NOPE' not found in the applicable \
               tables^ SELECT TOP ? \"Nope\" FROM";
    assert!(sql(msg, "SELECT TOP 1 \"Nope\" FROM Test129.Hint").is_none());
    let msg = "ERROR #5540: SQLCODE: -29 Message:  Field 'A' not found^ INSERT";
    let h = sql(msg, "INSERT INTO T (x) VALUES (\"a\")");
    assert_eq!(rule_of(&h), Some("double_quoted_string"));
    let h = sql(msg, "SELECT x FROM T WHERE x IN ('b', \"a\")");
    assert_eq!(rule_of(&h), Some("double_quoted_string"));
}

#[test]
fn a_misspelt_unquoted_field_gets_no_hint() {
    let msg = "ERROR #5540: SQLCODE: -29 Message:  Field 'NOPE' not found in the applicable \
               tables^ SELECT TOP ? Nope FROM";
    assert!(sql(msg, "SELECT TOP 1 Nope FROM Test129.Hint").is_none());
}

// ── reserved_word (research R5) ──────────────────────────────────────────────────────────────

#[test]
fn a_reserved_alias_gets_the_quoted_spelling() {
    for (upper, alias) in [
        ("LEVEL", "Level"),
        ("COUNT", "count"),
        ("FOUND", "FOUND"),
        ("ROWS", "Rows"),
    ] {
        let msg = format!(
            "ERROR #5540: SQLCODE: -1 Message:  IDENTIFIER expected, reserved word {upper} \
             found^ SELECT COUNT ( * ) AS {upper}"
        );
        let h = sql(
            &msg,
            &format!("SELECT COUNT(*) AS {alias} FROM Test129.Hint"),
        )
        .unwrap_or_else(|| panic!("{upper} has a rule"));
        assert_eq!(h.rule(), "reserved_word");
        assert!(h.text().contains(&format!("\"{alias}\"")), "{}", h.text());
        assert_eq!(h.skill(), "iris-sql");
    }
}

/// A reserved word that is not an alias (here a table name) has no `AS` before it, so the hint
/// takes the query's own spelling of the last match. Live capture, iris-dev-iris 2026-10-02.
#[test]
fn a_reserved_table_name_gets_the_query_spelling() {
    let h = sql(
        "ERROR #5540: SQLCODE: -1 Message:  IDENTIFIER expected, reserved word LEVEL found ^ SELECT Title FROM Test129 . Hint WHERE Title IN ( SELECT Title FROM LEVEL",
        "SELECT Title FROM Test129.Hint WHERE Title IN (SELECT Title FROM Level)",
    )
    .expect("reserved_word");
    assert_eq!(h.rule(), "reserved_word");
    assert!(h.text().contains("\"Level\""), "{}", h.text());
}

// ── nonstandard_insert (research R6) ─────────────────────────────────────────────────────────

#[test]
fn sqlite_and_mysql_insert_forms_get_the_duplicate_handling_hint() {
    let cases = [
        (
            "ERROR #5540: SQLCODE: -1 Message:  UPDATE expected, IDENTIFIER (IGNORE) found^ INSERT OR IGNORE",
            "INSERT OR IGNORE INTO Test129.Hint (Title) VALUES ('a')",
            "INSERT OR IGNORE",
        ),
        (
            "ERROR #5540: SQLCODE: -1 Message:  UPDATE expected, IDENTIFIER (REPLACE) found^ INSERT OR REPLACE",
            "INSERT OR REPLACE INTO Test129.Hint (Title) VALUES ('a')",
            "INSERT OR REPLACE",
        ),
        (
            "ERROR #5540: SQLCODE: -30 Message:  Table 'SQLUSER.IGNORE' not found",
            "INSERT IGNORE INTO Test129.Hint (Title) VALUES ('a')",
            "INSERT IGNORE",
        ),
        (
            "ERROR #5540: SQLCODE: -25 Message:  Input (ON) encountered after end of query^ INSERT INTO Test129 . Hint ( Title ) VALUES ( ? ) ON",
            "INSERT INTO Test129.Hint (Title) VALUES ('a') ON CONFLICT DO NOTHING",
            "ON CONFLICT",
        ),
    ];
    for (msg, query, form) in cases {
        let h = sql(msg, query).unwrap_or_else(|| panic!("{form} has a rule"));
        assert_eq!(h.rule(), "nonstandard_insert");
        assert!(h.text().contains(form), "{}", h.text());
        assert!(h.text().contains("-119"), "{}", h.text());
        assert_eq!(h.skill(), "iris-sql");
    }
}

#[test]
fn a_real_sqluser_ignore_table_miss_without_insert_ignore_gets_no_insert_hint() {
    let h = sql(
        "ERROR #5540: SQLCODE: -30 Message:  Table 'SQLUSER.IGNORE' not found",
        "SELECT * FROM Ignore",
    );
    assert_ne!(rule_of(&h), Some("nonstandard_insert"));
}

// ── runtime: sys_only_class (spec 125) ───────────────────────────────────────────────────────

#[test]
fn a_system_class_outside_sys_points_at_the_sys_namespace() {
    for class in [
        "Security.Applications",
        "Security.Users",
        "Security.Roles",
        "Config.Namespaces",
        "SYS.Database",
    ] {
        let h = runtime_error_hint(&class_missing(class), "USER")
            .unwrap_or_else(|| panic!("{class} in USER has a rule"));
        assert_eq!(h.rule(), "sys_only_class");
        assert!(h.text().contains(class), "{}", h.text());
        assert!(h.text().contains("\"%SYS\""), "{}", h.text());
        assert_eq!(h.skill(), "iris-agentic-dev");
    }
}

#[test]
fn already_in_sys_gets_no_hint() {
    for ns in ["%SYS", "%sys"] {
        assert!(runtime_error_hint(&class_missing("Security.Applications"), ns).is_none());
    }
}

#[test]
fn percent_packages_and_unknown_classes_get_no_hint() {
    for class in [
        "%SYS.ProcessQuery",
        "%SYSTEM.Security",
        "Nope.Missing",
        "SYSX.Thing",
    ] {
        assert!(
            runtime_error_hint(&class_missing(class), "USER").is_none(),
            "{class}"
        );
    }
}

#[test]
fn other_runtime_errors_get_no_hint() {
    let out = "ERROR: <UNDEFINED> Execute+3^IrisDevTmp.IrisDevRun1.1 *Security";
    assert!(runtime_error_hint(out, "USER").is_none());
}

// ── hint_ref and the coding pack (FR-001, FR-002) ────────────────────────────────────────────

#[test]
fn apply_sets_hint_and_hint_ref_with_the_pack_on() {
    let h = sql(
        &table_missing("SECURITY.USERS"),
        "SELECT * FROM Security.Users",
    )
    .unwrap();
    let mut v = serde_json::json!({"success": false});
    h.apply_with(&mut v, true);
    assert_eq!(v["hint"], h.text());
    assert_eq!(v["hint_ref"]["skill"], "iris-agentic-dev");
    assert_eq!(v["hint_ref"]["section"], h.section());
    assert!(v["hint_ref"]["why"].as_str().is_some_and(|s| !s.is_empty()));
    assert_eq!(v["hint_ref"].as_object().unwrap().len(), 3);
}

#[test]
fn apply_drops_hint_ref_with_the_pack_off_and_keeps_the_text() {
    let h = sql(
        &table_missing("SECURITY.USERS"),
        "SELECT * FROM Security.Users",
    )
    .unwrap();
    let mut on = serde_json::json!({});
    let mut off = serde_json::json!({});
    h.apply_with(&mut on, true);
    h.apply_with(&mut off, false);
    assert_eq!(on["hint"], off["hint"]);
    assert!(off.get("hint_ref").is_none());
}

/// `apply` reads the switch from the environment; `hint` is set whichever way it reads.
#[test]
fn apply_reads_the_switch_and_always_sets_hint() {
    let h = sql(
        &table_missing("SECURITY.USERS"),
        "SELECT * FROM Security.Users",
    )
    .unwrap();
    let mut v = serde_json::json!({});
    h.apply(&mut v);
    assert_eq!(v["hint"], h.text());
    assert_eq!(v.get("hint_ref").is_some(), coding_pack_on());
}

#[test]
fn coding_pack_switch_reads_off_values() {
    for off in ["off", "0", "false", "no", "OFF", " No "] {
        assert!(!coding_pack_from(Some(off)), "{off:?}");
    }
    for on in [None, Some(""), Some("on"), Some("1"), Some("yes")] {
        assert!(coding_pack_from(on), "{on:?}");
    }
}

// ── delete_callback_oid (CORPUS-40, transcripts 2026-10-10) ──────────────────────────────────
//
// Strings copied from a live compile on iris-dev-iris: `Method %OnDelete()` gives #5477 and
// `ClassMethod %OnDelete(pId As %String)` gives #5478. Five of six sessions on CORPUS-40 read one
// of these, fixed the signature, and killed the wrong node because the argument is an OID list.

fn class_method_error(class: &str, method: &str) -> String {
    format!(
        "ERROR #5477: Keyword signature error in {class}:Method:{method}, keyword 'ClassMethod' must be '1'"
    )
}

fn oid_signature_error(class: &str, method: &str) -> String {
    format!(
        "ERROR #5478: Keyword signature error in {class}:Method:{method}, keyword 'method argument/s signature' must be '%Library.ObjectIdentity' or its subclass"
    )
}

#[test]
fn a_delete_callback_given_the_wrong_signature_is_told_the_argument_is_an_oid() {
    for method in ["%OnDelete", "%OnAfterDelete"] {
        for msg in [
            class_method_error("Bench.Tracked", method),
            oid_signature_error("Bench.Tracked", method),
        ] {
            let h = compile_error_hint(&["Compiling class Bench.Tracked".into(), msg.clone()])
                .unwrap_or_else(|| panic!("no hint for {msg}"));
            assert_eq!(h.rule(), "delete_callback_oid");
            assert!(h.text().contains(method), "{}", h.text());
            assert!(h.text().contains("$$$oidPrimary(oid)"), "{}", h.text());
            assert!(h.text().contains("%ObjectIdentity"), "{}", h.text());
        }
    }
}

#[test]
fn the_hint_says_a_clean_compile_does_not_prove_the_id() {
    let h = compile_error_hint(&[oid_signature_error("A.B", "%OnDelete")]).unwrap();
    assert!(
        h.text().contains("delete a row"),
        "the agent stopped at the first clean compile: {}",
        h.text()
    );
}

#[test]
fn other_keyword_signature_errors_get_no_oid_hint() {
    // %OnAfterSave takes a plain Boolean; a wrong signature there is not an OID problem.
    let m = "ERROR #5478: Keyword signature error in A.B:Method:%OnAfterSave, keyword 'method argument/s signature' must be '%Library.Boolean'";
    assert!(compile_error_hint(&[m.into()]).is_none());
    assert!(compile_error_hint(&[class_method_error("A.B", "%OnAfterSave")]).is_none());
    assert!(compile_error_hint(&[
        "ERROR #5030: An error occurred while compiling class 'A.B'".into()
    ])
    .is_none());
    assert!(compile_error_hint(&[]).is_none());
}

#[test]
fn a_user_method_named_like_a_callback_prefix_is_not_matched() {
    assert!(compile_error_hint(&[class_method_error("A.B", "OnDelete")]).is_none());
    assert!(compile_error_hint(&[class_method_error("A.B", "%OnDeleteExtra")]).is_none());
}

// ── unknown_persistent_callback (IMP-0002 and IMP-0004 re-runs) ──────────────────────────────
//
// Live on iris-dev-iris 2026.2: a persistent class with `Method %OnBeforeDelete()` compiled
// clean and `%DeleteId` never called it; the `%OnDelete` class method beside it ran once.
// `%Dictionary.CompiledMethod` for %Library.Persistent has no %OnBeforeDelete and no
// %OnAfterRemove. Three of nine with-skills sessions invented one of them and reported success.

fn persistent(method_line: &str) -> String {
    format!("Class A.B Extends %Persistent\n{{\n\nProperty Name As %String;\n\n{method_line}\n{{\n    Quit $$$OK\n}}\n}}")
}

#[test]
fn an_invented_persistent_callback_gets_the_never_called_hint() {
    for m in [
        "%OnBeforeDelete",
        "%OnAfterRemove",
        "%OnBeforeRemove",
        "%OnDeleted",
    ] {
        for line in [
            format!("Method {m}() As %Status [ Private, ServerOnly = 1 ]"),
            format!("  ClassMethod {m}(oid As %ObjectIdentity) As %Status"),
        ] {
            let src = persistent(&line);
            let h = compiled_source_hint(&src).unwrap_or_else(|| panic!("no hint for {src}"));
            assert_eq!(h.rule(), "unknown_persistent_callback");
            assert!(h.text().contains(m), "{}", h.text());
            assert!(h.text().contains("never calls"), "{}", h.text());
            assert!(h.text().contains("%OnDelete"), "{}", h.text());
        }
    }
}

#[test]
fn every_real_persistent_callback_gets_no_hint() {
    for m in KNOWN_CALLBACKS {
        let src = persistent(&format!("Method {m}() As %Status"));
        assert!(compiled_source_hint(&src).is_none(), "{m}");
    }
    assert!(KNOWN_CALLBACKS.contains(&"%OnDelete") && KNOWN_CALLBACKS.contains(&"%OnAfterDelete"));
    assert!(!KNOWN_CALLBACKS.contains(&"%OnBeforeDelete"));
}

#[test]
fn only_a_class_that_extends_persistent_is_judged() {
    let m = "Method %OnAfterRemove() As %Status\n{\n    Quit $$$OK\n}";
    // Another superclass may define the callback, so the hint would be a guess.
    assert!(compiled_source_hint(&format!("Class A.B Extends Other.Base\n{{\n{m}\n}}")).is_none());
    assert!(
        compiled_source_hint(&format!("Class A.B Extends %RegisteredObject\n{{\n{m}\n}}"))
            .is_none()
    );
    assert!(compiled_source_hint(m).is_none());
    assert!(compiled_source_hint("").is_none());
    // The usual mixins add no %On* methods.
    let src = format!("Class A.B Extends (%Persistent, %Populate, %XML.Adaptor)\n{{\n{m}\n}}");
    assert!(compiled_source_hint(&src).is_some());
    let src = format!("Class A.B Extends %Library.Persistent\n{{\n{m}\n}}");
    assert!(compiled_source_hint(&src).is_some());
}

#[test]
fn a_comment_or_longer_name_is_not_a_callback_method() {
    let src = "Class A.B Extends %Persistent\n{\n// Method %OnAfterRemove is not a thing\nMethod Run() As %Status\n{\n    Quit $$$OK\n}\n}";
    assert!(compiled_source_hint(src).is_none());
}

// ── objects across iris_execute_method calls (CORPUS-40, 56-call session) ────────────────────
//
// Strings copied from the transcript and checked live: `%New` answers `1060@Bench.Tracked`, and
// `%Save` on the class answers `<METHOD DOES NOT EXIST> 148 Execute+7^IrisDevTmp.IrisDevRun… %Save,Bench.Tracked`.
// Each call is a new process, so the object is gone before the next call can use it.

const MISSING_SAVE: &str =
    "<METHOD DOES NOT EXIST> 148 Execute+7^IrisDevTmp.IrisDevRun01e4ed96a144.1 %Save,Bench.Tracked";

#[test]
fn a_new_object_reference_is_told_it_ends_with_the_call() {
    let h = execute_method_hint("Bench.Tracked", "%New", "1060@Bench.Tracked").unwrap();
    assert_eq!(h.rule(), "object_reference_result");
    assert!(h.text().contains("1060@Bench.Tracked"), "{}", h.text());
    assert!(h.text().contains("iris_execute"), "{}", h.text());
    assert!(h.text().contains("new process"), "{}", h.text());
}

#[test]
fn an_instance_method_on_the_class_is_told_there_is_no_object() {
    for m in ["%Save", "%Id", "%Reload", "%Close"] {
        let out = format!("<METHOD DOES NOT EXIST> 148 Execute+7^IrisDevTmp.X.1 {m},Bench.Tracked");
        let h = execute_method_hint("Bench.Tracked", m, &out)
            .unwrap_or_else(|| panic!("no hint for {m}"));
        assert_eq!(h.rule(), "instance_method_on_class");
        assert!(h.text().contains(m), "{}", h.text());
        assert!(h.text().contains("iris_execute"), "{}", h.text());
    }
    let _ = MISSING_SAVE;
}

#[test]
fn ordinary_results_and_other_misses_get_no_object_hint() {
    assert!(execute_method_hint("A.B", "Total", "5").is_none());
    assert!(execute_method_hint("A.B", "%OpenId", "").is_none());
    assert!(
        execute_method_hint("A.B", "Total", "12@steps").is_none(),
        "not an object reference"
    );
    assert!(execute_method_hint(
        "A.B",
        "Nope",
        "<METHOD DOES NOT EXIST> 148 Execute+7^X.1 Nope,A.B"
    )
    .is_none());
    assert!(execute_method_hint(
        "A.B",
        "%DeleteId",
        "<METHOD DOES NOT EXIST> 148 Execute+7^X.1 %DeleteIdx,A.B"
    )
    .is_none());
}

// ── the rule table (FR-003, FR-004) ──────────────────────────────────────────────────────────

#[test]
fn every_rule_has_a_matcher_and_every_matcher_a_rule() {
    let mut in_file: Vec<&str> = rules().iter().map(|r| r.id.as_str()).collect();
    let mut in_code: Vec<&str> = matcher_ids().to_vec();
    in_file.sort_unstable();
    in_code.sort_unstable();
    assert_eq!(in_file, in_code);
    assert_eq!(in_file.len(), 11);
}

/// FR-003: the skill reference lives only in `hint_ref`, so turning the pack off really drops it.
#[test]
fn no_hint_text_names_a_bundled_skill() {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../skills/skills");
    let names: Vec<String> = std::fs::read_dir(&dir)
        .unwrap()
        .filter_map(|e| e.ok())
        .filter(|e| e.path().join("SKILL.md").exists())
        .map(|e| e.file_name().to_string_lossy().into_owned())
        .collect();
    assert!(names.len() > 10);
    for r in rules() {
        for n in &names {
            assert!(!r.text.contains(n.as_str()), "rule {} names {n}", r.id);
        }
        assert!(!r.text.contains("Skill "), "rule {}", r.id);
        assert!(r.text.chars().count() <= 400, "rule {} too long", r.id);
    }
}

/// FR-001: a hint that sends the agent to a section that isn't there is a wrong hint.
#[test]
fn every_cited_skill_section_exists() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    assert_eq!(cited_sections().len(), 11);
    for (skill, heading) in cited_sections() {
        let path = root.join(format!("skills/skills/{skill}/SKILL.md"));
        let text =
            std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        assert!(
            text.lines()
                .any(|l| l.starts_with('#') && l.trim_start_matches('#').trim() == heading),
            "{skill}/SKILL.md has no heading {heading:?}"
        );
    }
}

#[test]
fn every_placeholder_in_a_template_is_filled() {
    let cases: Vec<Hint> = vec![
        sql(SQL_12_SELECT, "").unwrap(),
        sql(&table_missing("SECURITY.USERS"), "Security.Users").unwrap(),
        sql(&table_missing("SUB.DEEP"), "Test129.Sub.Deep").unwrap(),
        sql(SQL_29_HELLO, "WHERE Title = \"hello\"").unwrap(),
        sql(
            "ERROR #5540: SQLCODE: -1 Message:  IDENTIFIER expected, reserved word LEVEL found^ SELECT",
            "SELECT 1 AS Level",
        )
        .unwrap(),
        sql(
            "ERROR #5540: SQLCODE: -30 Message:  Table 'SQLUSER.IGNORE' not found",
            "INSERT IGNORE INTO T (a) VALUES (1)",
        )
        .unwrap(),
        runtime_error_hint(&class_missing("Security.Users"), "USER").unwrap(),
        compile_error_hint(&[oid_signature_error("Bench.CapB", "%OnDelete")]).unwrap(),
        compiled_source_hint(&persistent("Method %OnAfterRemove() As %Status")).unwrap(),
        execute_method_hint("Bench.Tracked", "%New", "1060@Bench.Tracked").unwrap(),
        execute_method_hint("Bench.Tracked", "%Save", "<METHOD DOES NOT EXIST> 148 Execute+7^IrisDevTmp.IrisDevRun01e4ed96a144.1 %Save,Bench.Tracked").unwrap(),
    ];
    let mut seen: Vec<&str> = cases.iter().map(|h| h.rule()).collect();
    seen.sort_unstable();
    seen.dedup();
    assert_eq!(seen.len(), 11, "one case per rule");
    for h in &cases {
        assert!(
            !h.text().contains('{') && !h.text().contains('}'),
            "{}: {}",
            h.rule(),
            h.text()
        );
    }
}

// ── description (spec 125 FR-006) ────────────────────────────────────────────────────────────

#[test]
fn iris_execute_description_names_the_sys_only_packages() {
    let tools = IrisTools::new_with_toolset(None, Toolset::Merged).expect("IrisTools::new");
    let desc = tools
        .tool_catalogue()
        .into_iter()
        .find(|e| e.name == "iris_execute")
        .and_then(|e| e.description)
        .expect("iris_execute is registered");
    for needle in ["Security.*", "Config.*", "SYS.*", "namespace: \"%SYS\""] {
        assert!(
            desc.contains(needle),
            "iris_execute description lacks {needle:?}"
        );
    }
}

// ── matchers give up cleanly ─────────────────────────────────────────────────────────────────
//
// These inputs are synthetic, unlike the rest of this file. They check that each matcher returns
// no hint when part of the message it reads is missing, not what IRIS says.

#[test]
fn messages_missing_the_part_a_rule_reads_get_no_hint() {
    for msg in [
        "connection refused",
        "ERROR #5540: SQLCODE: -99999999999 Message:  overflow",
        "ERROR #5540: SQLCODE: -1 Message:  something else^ SELECT",
        "ERROR #5540: SQLCODE: -29 Message:  something else",
        "ERROR #5540: SQLCODE: -30 Message:  something else",
        "ERROR #5540: SQLCODE: -30 Message:  Table 'NODOT' not found",
        "ERROR #5540: SQLCODE: -30 Message:  Table 'SQLUSER.NOPE' not found",
    ] {
        assert!(sql(msg, "SELECT * FROM Nope").is_none(), "{msg}");
    }
    assert!(runtime_error_hint("ERROR: <UNDEFINED> x", "USER").is_none());
    assert!(runtime_error_hint("<CLASS DOES NOT EXIST>", "USER").is_none());
}
