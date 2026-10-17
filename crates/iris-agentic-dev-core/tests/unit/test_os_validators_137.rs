//! 137: every caller-supplied name that is spliced into ObjectScript, SQL or a URL goes through a
//! validator first. These lists pin what each one accepts (names IRIS really uses) and refuses (text
//! that would close a literal or a call and run something else).

use iris_agentic_dev_core::objectscript::{
    os_str_expr, validate_class_name, validate_global_name, validate_method_name,
    validate_namespace, validate_routine_name, validate_sql_identifier, validate_timestamp,
};

/// Text that turns a splice into code, whichever quoting the site uses.
const CRAFTED: &[&str] = &[
    "X\" Kill ^Y Set z=\"",
    "X) Kill ^Y Set q=$Get(^X",
    "X' OR 1=1 --",
    "X Kill ^Y",
    "X\nKill ^Y",
    "X,Y",
    "@X",
    "X;Y",
    "X{Y}",
    "X$Y",
    "",
];

fn assert_accepts(name: &str, f: fn(&str) -> Result<(), serde_json::Value>, ok: &[&str]) {
    assert!(!ok.is_empty());
    for v in ok {
        assert!(f(v).is_ok(), "{name} must accept {v:?}: {:?}", f(v));
    }
}

fn assert_refuses(
    name: &str,
    f: fn(&str) -> Result<(), serde_json::Value>,
    code: &str,
    bad: &[&str],
) {
    assert!(!bad.is_empty());
    for v in bad {
        let err = f(v).expect_err(&format!("{name} must refuse {v:?}"));
        assert_eq!(err["error_code"], code, "{name} on {v:?}: {err}");
        assert_eq!(err["success"], false);
        assert!(
            err["message"].as_str().is_some_and(|m| !m.is_empty()),
            "{err}"
        );
    }
}

#[test]
fn class_names() {
    assert_accepts(
        "class",
        validate_class_name,
        &[
            "MyApp.Patient",
            "%Library.String",
            "Ens.Director",
            "%ZEN.Component.page",
            "HS.FHIR.DTL.vR4.Model.Resource.Patient",
            "A",
            "IADTest136.IntakeRule",
        ],
    );
    assert_refuses("class", validate_class_name, "INVALID_CLASS_NAME", CRAFTED);
    assert_refuses(
        "class",
        validate_class_name,
        "INVALID_CLASS_NAME",
        &["1A.B", ".A", "A.", "A..B", "%%A", "A.%B", "A.1B"],
    );
}

#[test]
fn routine_and_document_names() {
    assert_accepts(
        "routine",
        validate_routine_name,
        &[
            "MyRoutine",
            "MyRoutine.mac",
            "%SYS.Something.int",
            "IAD.Probe.BP.1.int",
            "MyApp.Patient.cls",
            "MyApp.Macros.inc",
            "MyApp.Flow.bpl",
            "MyApp.Map.dtl",
            "%ZSTART",
        ],
    );
    assert_refuses(
        "routine",
        validate_routine_name,
        "INVALID_ROUTINE_NAME",
        CRAFTED,
    );
    assert_refuses(
        "routine",
        validate_routine_name,
        "INVALID_ROUTINE_NAME",
        &["A..mac", ".mac", "A.mac.", "A/B.mac"],
    );
}

#[test]
fn namespaces() {
    assert_accepts(
        "namespace",
        validate_namespace,
        &[
            "USER",
            "%SYS",
            "BENCHMARK",
            "HSLIB",
            "FHIR-SERVER",
            "my_ns",
            "Ns2",
        ],
    );
    assert_refuses(
        "namespace",
        validate_namespace,
        "INVALID_NAMESPACE",
        CRAFTED,
    );
    assert_refuses(
        "namespace",
        validate_namespace,
        "INVALID_NAMESPACE",
        &["1USER", "US ER", "USER'", "a.b", "^USER"],
    );
}

#[test]
fn method_names() {
    assert_accepts(
        "method",
        validate_method_name,
        &[
            "OnRequest",
            "%New",
            "%OpenId",
            "GetProductionStatus",
            "Test1",
        ],
    );
    assert_refuses(
        "method",
        validate_method_name,
        "INVALID_METHOD_NAME",
        CRAFTED,
    );
    assert_refuses(
        "method",
        validate_method_name,
        "INVALID_METHOD_NAME",
        &["A.B", "1A", "%%A"],
    );
}

#[test]
fn sql_identifiers() {
    assert_accepts(
        "sql",
        validate_sql_identifier,
        &[
            "Ens_Rule.RuleSet",
            "Sample.Person",
            "%Dictionary.CompiledClass",
            "INFORMATION_SCHEMA.TABLES",
            "Person",
            "\"My Schema\".\"My Table\"",
            "SQLUser.Bench_Q2",
        ],
    );
    assert_refuses(
        "sql",
        validate_sql_identifier,
        "INVALID_SQL_IDENTIFIER",
        CRAFTED,
    );
    assert_refuses(
        "sql",
        validate_sql_identifier,
        "INVALID_SQL_IDENTIFIER",
        &["a.b.c", "\"a\"\"b\"", "a b", "a.", ".a"],
    );
}

#[test]
fn timestamps() {
    assert_accepts(
        "ts",
        validate_timestamp,
        &[
            "2026-10-17",
            "2026-10-17 09:30:00",
            "2026-10-17 09:30:00.123",
        ],
    );
    assert_refuses("ts", validate_timestamp, "INVALID_TIMESTAMP", CRAFTED);
    assert_refuses(
        "ts",
        validate_timestamp,
        "INVALID_TIMESTAMP",
        &[
            "2026-10-17\" Kill ^Y",
            "yesterday",
            "2026-1-7",
            "2026-10-17 9:30",
        ],
    );
}

#[test]
fn global_names_still_validate_from_their_new_home() {
    assert!(validate_global_name("IrisDevTest.G146").is_ok());
    assert_eq!(
        validate_global_name("X) Kill ^Y").unwrap_err()["error_code"],
        "INVALID_GLOBAL_NAME"
    );
}

#[test]
fn os_str_expr_quotes_what_it_splices() {
    assert_eq!(os_str_expr(""), "\"\"");
    assert_eq!(os_str_expr("a\"b"), "\"a\"\"b\"");
    let with_newline = os_str_expr("a\nb");
    assert!(with_newline.contains("$CHAR(10)"), "{with_newline}");
    assert!(!with_newline.contains('\n'), "{with_newline}");
}
