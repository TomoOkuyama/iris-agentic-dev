use iris_agentic_dev_core::tools::doc_search::{
    build_request_body, parse_hits, IrisDocSearchParams,
};

mod build_request_body_tests {
    use super::*;

    #[test]
    fn minimal_query_no_filters() {
        let p = IrisDocSearchParams {
            query: "SQL execution".to_string(),
            version: None,
            product: None,
            hits: None,
        };
        let body = build_request_body(&p);
        assert_eq!(body["query"], "SQL execution");
        assert_eq!(body["hitsPerPage"], 5);
        // no facetFilters key when no filters
        assert!(body.get("facetFilters").is_none());
    }

    #[test]
    fn version_filter_added() {
        let p = IrisDocSearchParams {
            query: "coverage".to_string(),
            version: Some("2025.1".to_string()),
            product: None,
            hits: None,
        };
        let body = build_request_body(&p);
        let filters = body["facetFilters"].as_array().unwrap();
        assert!(filters.iter().any(|f| f.as_str() == Some("version:2025.1")));
    }

    #[test]
    fn product_filter_added() {
        let p = IrisDocSearchParams {
            query: "adapter".to_string(),
            version: None,
            product: Some("InterSystems IRIS".to_string()),
            hits: None,
        };
        let body = build_request_body(&p);
        let filters = body["facetFilters"].as_array().unwrap();
        assert!(filters
            .iter()
            .any(|f| f.as_str() == Some("product:InterSystems IRIS")));
    }

    #[test]
    fn both_filters_added() {
        let p = IrisDocSearchParams {
            query: "security".to_string(),
            version: Some("2026.1".to_string()),
            product: Some("InterSystems IRIS".to_string()),
            hits: None,
        };
        let body = build_request_body(&p);
        let filters = body["facetFilters"].as_array().unwrap();
        assert_eq!(filters.len(), 2);
    }

    #[test]
    fn hits_capped_at_10() {
        let p = IrisDocSearchParams {
            query: "test".to_string(),
            version: None,
            product: None,
            hits: Some(50),
        };
        let body = build_request_body(&p);
        assert_eq!(body["hitsPerPage"], 10);
    }

    #[test]
    fn hits_custom_within_range() {
        let p = IrisDocSearchParams {
            query: "test".to_string(),
            version: None,
            product: None,
            hits: Some(7),
        };
        let body = build_request_body(&p);
        assert_eq!(body["hitsPerPage"], 7);
    }

    #[test]
    fn attributes_to_retrieve_present() {
        let p = IrisDocSearchParams {
            query: "x".to_string(),
            version: None,
            product: None,
            hits: None,
        };
        let body = build_request_body(&p);
        let attrs = body["attributesToRetrieve"].as_array().unwrap();
        let attr_strs: Vec<&str> = attrs.iter().filter_map(|v| v.as_str()).collect();
        assert!(attr_strs.contains(&"title"));
        assert!(attr_strs.contains(&"URL"));
        assert!(attr_strs.contains(&"text"));
        assert!(attr_strs.contains(&"breadcrumbs"));
        assert!(attr_strs.contains(&"version"));
        assert!(attr_strs.contains(&"product"));
    }
}

mod parse_hits_tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn empty_hits_array() {
        let resp = json!({ "nbHits": 0, "hits": [] });
        let hits = parse_hits(&resp);
        assert!(hits.is_empty());
    }

    #[test]
    fn single_hit_all_fields() {
        let resp = json!({
            "nbHits": 1,
            "hits": [{
                "title": "Dynamic SQL",
                "URL": "https://docs.intersystems.com/iris20251/...",
                "text": "Dynamic SQL allows you to construct SQL statements at runtime.",
                "breadcrumbs": "Development > SQL > Dynamic SQL",
                "version": "2025.1",
                "product": "InterSystems IRIS"
            }]
        });
        let hits = parse_hits(&resp);
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0]["title"], "Dynamic SQL");
        assert_eq!(hits[0]["version"], "2025.1");
        assert!(hits[0]["excerpt"]
            .as_str()
            .unwrap()
            .contains("Dynamic SQL allows"));
    }

    #[test]
    fn text_truncated_at_600_chars() {
        let long_text = "x".repeat(1000);
        let resp = json!({
            "hits": [{
                "title": "T",
                "URL": "u",
                "text": long_text,
                "breadcrumbs": "b",
                "version": "2025.1",
                "product": "InterSystems IRIS"
            }]
        });
        let hits = parse_hits(&resp);
        let excerpt = hits[0]["excerpt"].as_str().unwrap();
        assert!(excerpt.len() <= 600);
    }

    #[test]
    fn missing_fields_default_empty() {
        let resp = json!({
            "hits": [{ "title": "Minimal" }]
        });
        let hits = parse_hits(&resp);
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0]["title"], "Minimal");
        assert_eq!(hits[0]["url"], "");
        assert_eq!(hits[0]["excerpt"], "");
        assert_eq!(hits[0]["breadcrumbs"], "");
    }

    #[test]
    fn multiple_hits_returned() {
        let resp = json!({
            "hits": [
                {"title": "A", "URL": "u1", "text": "ta", "breadcrumbs": "b1", "version": "2025.1", "product": "IRIS"},
                {"title": "B", "URL": "u2", "text": "tb", "breadcrumbs": "b2", "version": "2025.1", "product": "IRIS"},
                {"title": "C", "URL": "u3", "text": "tc", "breadcrumbs": "b3", "version": "2025.1", "product": "IRIS"}
            ]
        });
        let hits = parse_hits(&resp);
        assert_eq!(hits.len(), 3);
        assert_eq!(hits[1]["title"], "B");
    }

    #[test]
    fn missing_hits_key_returns_empty() {
        let resp = json!({ "nbHits": 0 });
        let hits = parse_hits(&resp);
        assert!(hits.is_empty());
    }
}

mod params_tests {
    use super::*;

    #[test]
    fn default_hits_is_none() {
        let p = IrisDocSearchParams {
            query: "test".to_string(),
            version: None,
            product: None,
            hits: None,
        };
        assert!(p.hits.is_none());
    }

    #[test]
    fn all_optional_fields_none() {
        let p = IrisDocSearchParams {
            query: "anything".to_string(),
            version: None,
            product: None,
            hits: None,
        };
        // Should not panic; build_request_body handles all-None gracefully
        let body = build_request_body(&p);
        assert_eq!(body["query"], "anything");
    }
}

/// TPRM-6602: the Algolia key is read from the docs page at run time, not kept in the repo. The
/// key docs.intersystems.com serves turned out to carry write rights, so it will be rotated; a
/// copy in the source would break the tool the day it is, and is a key in the repo either way.
mod algolia_meta_tests {
    use iris_agentic_dev_core::tools::doc_search::{parse_algolia_meta, AlgoliaCreds};

    const PAGE: &str = r#"<head><title>x</title>
<meta class="algolia" name="ALG-AppID" data-type="string" content="AB12CD34EF"/>
<meta class="algolia" name="ALG-Index" data-type="string" content="docs"/>
<meta class="algolia" name="ALG-SearchKey" data-type="string" content="TESTKEYtestkeyTESTKEYtestkey0000"/>
<meta class="algolia" name="ALG-Version" data-type="string" content="version:'2026.2'"/>
</head>"#;

    #[test]
    fn reads_the_app_id_index_and_key_from_the_meta_tags() {
        assert_eq!(
            parse_algolia_meta(PAGE),
            Some(AlgoliaCreds {
                app_id: "AB12CD34EF".into(),
                index: "docs".into(),
                search_key: "TESTKEYtestkeyTESTKEYtestkey0000".into(),
            })
        );
    }

    #[test]
    fn a_page_without_the_key_gives_none() {
        let page = PAGE.replace("ALG-SearchKey", "ALG-Other");
        assert_eq!(parse_algolia_meta(&page), None);
        assert_eq!(parse_algolia_meta("<html></html>"), None);
    }

    /// The app id becomes part of a hostname and the key a header value, so a value that is not
    /// plainly an id is refused rather than sent.
    #[test]
    fn values_that_are_not_plain_ids_are_refused() {
        for (from, to) in [
            ("AB12CD34EF", "evil.example.com/x"),
            ("AB12CD34EF", "AB12"),
            ("docs", "docs/../keys"),
            (
                "TESTKEYtestkeyTESTKEYtestkey0000",
                "TESTKEYtestkey TESTKEYtestkey000",
            ),
            ("TESTKEYtestkeyTESTKEYtestkey0000", "short"),
        ] {
            let page = PAGE.replace(from, to);
            assert_eq!(parse_algolia_meta(&page), None, "{to}");
        }
    }
}
