//! CORPUS-40: the claim behind the `delete_callback_oid` hint and the guardrails section.
//!
//! `%OnDelete` takes an OID. Using it as the id compiles clean and leaves the marker behind; the
//! `$$$oidPrimary(oid)` spelling clears it; the instance-method spelling and the plain-argument
//! spelling are refused with the errors the hint matches. Each test builds `IadLiveCb.*` classes
//! and drops them at the end.
//!
//! Run with:
//!   IRIS_HOST=localhost IRIS_WEB_PORT=52780 IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS \
//!   cargo test --features testing --test integration test_delete_callback_oid_live -- \
//!     --ignored --test-threads=1

use iris_agentic_dev_core::iris::connection::{
    is_generator_error, CompileResult, DiscoverySource, IrisConnection,
};
use iris_agentic_dev_core::tools::error_hints::compile_error_hint;

const NS: &str = "USER";

fn conn() -> Option<(IrisConnection, reqwest::Client)> {
    let host = std::env::var("IRIS_HOST").unwrap_or_default();
    if host.is_empty() {
        if std::env::var("IAD_ALLOW_SKIP").is_ok() {
            eprintln!("SKIP (IAD_ALLOW_SKIP set): IRIS_HOST unset");
            return None;
        }
        panic!(
            "IRIS_HOST unset. This test proves a skill claim against live IRIS; without IRIS it \
             asserts nothing, so it fails instead of passing quietly.\n\
             Set: IRIS_HOST=localhost IRIS_WEB_PORT=52780 IRIS_USERNAME=_SYSTEM IRIS_PASSWORD=SYS\n\
             Or opt into skipping deliberately: IAD_ALLOW_SKIP=1"
        );
    }
    let port = std::env::var("IRIS_WEB_PORT").unwrap_or_else(|_| "52780".into());
    let user = std::env::var("IRIS_USERNAME").unwrap_or_else(|_| "_SYSTEM".into());
    let pass = std::env::var("IRIS_PASSWORD").unwrap_or_else(|_| "SYS".into());
    let conn = IrisConnection::new(
        format!("http://{host}:{port}"),
        NS,
        user,
        pass,
        DiscoverySource::EnvVar,
    );
    Some((conn, reqwest::Client::new()))
}

async fn put_and_compile(
    c: &IrisConnection,
    client: &reqwest::Client,
    doc: &str,
    src: &str,
) -> CompileResult {
    let url = c.versioned_ns_url(
        NS,
        &format!("/doc/{}?ignoreConflict=1", urlencoding::encode(doc)),
    );
    let lines: Vec<&str> = src.lines().collect();
    let resp = client
        .put(&url)
        .basic_auth(&c.username, Some(&c.password))
        .json(&serde_json::json!({"enc": false, "content": lines}))
        .send()
        .await
        .expect("PUT must reach IRIS");
    assert!(resp.status().is_success(), "PUT {doc}: {}", resp.status());
    c.compile_document(doc, NS, "cuk", client)
        .await
        .expect("compile request must reach IRIS")
}

async fn run(c: &IrisConnection, client: &reqwest::Client, code: &str) -> String {
    let out = c
        .execute_via_generator(code, NS, client)
        .await
        .expect("execute request must reach IRIS");
    assert!(!is_generator_error(&out), "IRIS run failed: {out}");
    out.trim().to_string()
}

fn class(name: &str, delete: &str) -> String {
    format!(
        "Class {name} Extends %Persistent
{{

Property Name As %String;

Method %OnAfterSave(pInsert As %Boolean) As %Status [ Private, ServerOnly = 1 ]
{{
    Set ^IadLiveCb(\"{name}\", ..%Id()) = 1
    Quit $$$OK
}}

{delete}

}}"
    )
}

/// Save one row, delete it, and report `marker-after-save|marker-after-delete`.
async fn save_then_delete(c: &IrisConnection, client: &reqwest::Client, name: &str) -> String {
    let out = run(
        c,
        client,
        &format!(
            " Set o=##class({name}).%New(),o.Name=\"a\"\n \
             Set sc=o.%Save(),id=o.%Id(),m1=$Data(^IadLiveCb(\"{name}\",id))\n \
             Set sc2=##class({name}).%DeleteId(id)\n \
             Write \"~[\",m1,\"|\",$Data(^IadLiveCb(\"{name}\",id)),\"|\",$System.Status.IsOK(sc2),\"]~\""
        ),
    )
    .await;
    let start = out.rfind("~[").expect("marker") + 2;
    let end = out[start..].find("]~").expect("end") + start;
    out[start..end].to_string()
}

async fn drop(c: &IrisConnection, client: &reqwest::Client, names: &[&str]) {
    for n in names {
        let _ = c
            .execute_via_generator(
                &format!(" Kill ^IadLiveCb(\"{n}\")\n Do $system.OBJ.Delete(\"{n}\",\"e-d\")"),
                NS,
                client,
            )
            .await;
    }
}

#[tokio::test]
#[ignore]
async fn the_oid_primary_spelling_clears_the_marker_and_the_bare_argument_does_not() {
    let Some((c, client)) = conn() else { return };
    let good = "IadLiveCb.Good";
    let bad = "IadLiveCb.Bad";
    let good_src = class(
        good,
        "ClassMethod %OnDelete(oid As %ObjectIdentity) As %Status [ Private, ServerOnly = 1 ]
{
    Kill ^IadLiveCb(\"IadLiveCb.Good\", $$$oidPrimary(oid))
    Quit $$$OK
}",
    );
    let bad_src = class(
        bad,
        "ClassMethod %OnDelete(pId As %Library.ObjectIdentity) As %Status [ Private, ServerOnly = 1 ]
{
    Kill ^IadLiveCb(\"IadLiveCb.Bad\", pId)
    Quit $$$OK
}",
    );
    let r = put_and_compile(&c, &client, "IadLiveCb.Good.cls", &good_src).await;
    assert!(r.success(), "{:?}", r.errors);
    let r = put_and_compile(&c, &client, "IadLiveCb.Bad.cls", &bad_src).await;
    assert!(
        r.success(),
        "the wrong id compiles clean, which is the trap: {:?}",
        r.errors
    );

    // marker after save | marker after delete | %DeleteId returned OK
    assert_eq!(save_then_delete(&c, &client, good).await, "1|0|1");
    assert_eq!(
        save_then_delete(&c, &client, bad).await,
        "1|1|1",
        "the OID list is not the id, so the marker survives a delete that reports success"
    );
    drop(&c, &client, &[good, bad]).await;
}

#[tokio::test]
#[ignore]
async fn the_two_signature_errors_are_what_the_hint_matches() {
    let Some((c, client)) = conn() else { return };
    for (name, delete, code) in [
        (
            "IadLiveCb.Inst",
            "Method %OnDelete() As %Status [ Private, ServerOnly = 1 ]\n{\n    Quit $$$OK\n}",
            "#5477",
        ),
        (
            "IadLiveCb.Plain",
            "ClassMethod %OnDelete(pId As %String) As %Status [ Private, ServerOnly = 1 ]\n{\n    Quit $$$OK\n}",
            "#5478",
        ),
        (
            "IadLiveCb.After",
            "ClassMethod %OnAfterDelete(pId As %String) As %Status [ Private, ServerOnly = 1 ]\n{\n    Quit $$$OK\n}",
            "#5478",
        ),
    ] {
        let r = put_and_compile(&c, &client, &format!("{name}.cls"), &class(name, delete)).await;
        assert!(!r.success(), "{name} must not compile");
        let lines: Vec<String> = r.errors.iter().chain(r.console.iter()).cloned().collect();
        assert!(
            lines.iter().any(|l| l.contains(code)),
            "{name}: expected {code} in {lines:?}"
        );
        let h = compile_error_hint(&lines).unwrap_or_else(|| panic!("{name}: no hint in {lines:?}"));
        assert_eq!(h.rule(), "delete_callback_oid");
        drop(&c, &client, &[name]).await;
    }
}

/// The wiring, not just the matcher: both tools an agent compiles with hand back the hint, and a
/// clean compile hands back none.
#[tokio::test]
#[ignore]
async fn iris_doc_put_and_iris_compile_both_carry_the_hint() {
    let Some((c, client)) = conn() else { return };
    let t = iris_agentic_dev_core::tools::IrisTools::new(Some(c.clone())).expect("IrisTools::new");
    let name = "IadLiveCb.Wired";
    let bad = class(
        name,
        "ClassMethod %OnDelete(pId As %String) As %Status [ Private, ServerOnly = 1 ]\n{\n    Quit $$$OK\n}",
    );
    let call = |tool: &'static str, args: serde_json::Value| {
        let t = &t;
        async move {
            let r = t.call_for_test(tool, args).await.expect("call");
            serde_json::from_str::<serde_json::Value>(&r.content[0].as_text().unwrap().text)
                .expect("json")
        }
    };

    let put = call(
        "iris_doc",
        serde_json::json!({"mode":"put","name":"IadLiveCb.Wired.cls","content":bad,"compile":true,"namespace":NS}),
    )
    .await;
    assert_eq!(put["compiled"], false, "{put}");
    assert!(
        put["hint"]
            .as_str()
            .unwrap_or("")
            .contains("$$$oidPrimary(oid)"),
        "{put}"
    );
    assert_eq!(put["hint_ref"]["skill"], "objectscript-guardrails");

    let comp = call(
        "iris_compile",
        serde_json::json!({"target":"IadLiveCb.Wired.cls","namespace":NS,"flags":"cuk"}),
    )
    .await;
    assert_eq!(comp["success"], false, "{comp}");
    assert!(
        comp["hint"].as_str().unwrap_or("").contains("%OnDelete"),
        "{comp}"
    );

    let good = class(
        name,
        "ClassMethod %OnDelete(oid As %ObjectIdentity) As %Status [ Private, ServerOnly = 1 ]\n{\n    Kill ^IadLiveCb(\"IadLiveCb.Wired\", $$$oidPrimary(oid))\n    Quit $$$OK\n}",
    );
    let ok = call(
        "iris_doc",
        serde_json::json!({"mode":"put","name":"IadLiveCb.Wired.cls","content":good,"compile":true,"namespace":NS}),
    )
    .await;
    assert_eq!(ok["compiled"], true, "{ok}");
    assert!(
        ok.get("hint").is_none(),
        "a clean compile gets no hint: {ok}"
    );
    drop(&c, &client, &[name]).await;
}
