//! Open issues fixed for 1.6.0.

/// #139: on native Windows IRIS `$IO` comes back lower-cased while the temp-file name keeps its
/// case, so the exact comparison in the capture check failed every call since 1.3.2.
#[test]
fn capture_check_compares_the_device_without_case() {
    let lines = iris_agentic_dev_core::iris::connection::IrisConnection::build_exec_class_for_test(
        "IrisDevTmp.X",
        "",
        "Write 1",
    );
    let code = lines.join("\n");
    assert!(
        !code.contains("If devio'=tmpfile"),
        "an exact $IO comparison fails on Windows: {code}"
    );
    assert!(
        code.contains(r#"$ZConvert(devio,"L")'=$ZConvert(tmpfile,"L")"#),
        "the capture check must compare without case"
    );
}

/// #144: production item names often hold spaces, which a Mermaid node ID cannot.
#[test]
fn production_diagram_ids_are_valid_mermaid() {
    use iris_agentic_dev_core::tools::admin_tools::build_production_diagram;
    let items = vec![
        (
            "From DEMO LabService ADT".to_string(),
            "EnsLib.HL7.Service.FileService".to_string(),
            true,
        ),
        (
            "To-Lab \"Main\"".to_string(),
            "EnsLib.HL7.Operation.TCPOperation".to_string(),
            false,
        ),
        (
            "From DEMO LabService_ADT".to_string(),
            "X.Y".to_string(),
            true,
        ),
        ("9Lives".to_string(), "X.Z".to_string(), true),
    ];
    let d = build_production_diagram("APPPKG.FoundationProduction", &items);
    let id_re = regex::Regex::new(r"^[A-Za-z_][A-Za-z0-9_]*$").unwrap();
    let mut ids = Vec::new();
    for line in d.lines().skip(1) {
        let line = line.trim();
        let id = if let Some((a, b)) = line.split_once(" --> ") {
            assert!(id_re.is_match(a) && id_re.is_match(b), "edge ids: {line}");
            continue;
        } else {
            line.split('[').next().unwrap()
        };
        assert!(id_re.is_match(id), "node id {id:?} in {line:?}");
        ids.push(id.to_string());
    }
    let unique: std::collections::HashSet<_> = ids.iter().collect();
    assert_eq!(unique.len(), ids.len(), "two items got one id: {d}");
    assert!(
        d.contains("From DEMO LabService ADT"),
        "the label keeps the real name: {d}"
    );
    assert!(
        !d.contains("To-Lab \"Main\""),
        "a quote inside a label must be escaped: {d}"
    );
    assert!(d.contains(":::disabled"), "{d}");
}
