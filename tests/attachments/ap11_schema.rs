//! AP11, the schema half: `contracts/attachment.v1.schema.json` describes
//! exactly what the core serializes: the attachment reference, the kind,
//! the readiness states and every failure reason. The in-repo checker fully
//! enforces it. (The CLI half, `--json` matching the text, is phase 2.)

use openwiz_core::attachment::{
    ATTACHMENT_ID_MAX_LEN, ATTACHMENT_SCHEMA_ID, AttachmentId, AttachmentRef, FailReason, Kind,
    Readiness, SAFE_NAME_MAX_BYTES, SafeName, Sha256,
};
use serde_json::json;

use crate::support::*;

/// Every failure reason, listed by hand. A reason added to the core
/// without a line here fails to compile in `_exhaustive`.
const EVERY_REASON: [FailReason; 12] = [
    FailReason::UnsupportedHeif,
    FailReason::TypeUnclear,
    FailReason::ExtensionMismatch,
    FailReason::ImageTooLarge,
    FailReason::FileTooLarge,
    FailReason::ImageTypedFileTooLarge,
    FailReason::Folder,
    FailReason::LowDisk,
    FailReason::SizeMismatch,
    FailReason::ConnectionLost,
    FailReason::SignedOut,
    FailReason::Unreadable,
];

fn _exhaustive(reason: FailReason) {
    match reason {
        FailReason::UnsupportedHeif
        | FailReason::TypeUnclear
        | FailReason::ExtensionMismatch
        | FailReason::ImageTooLarge
        | FailReason::FileTooLarge
        | FailReason::ImageTypedFileTooLarge
        | FailReason::Folder
        | FailReason::LowDisk
        | FailReason::SizeMismatch
        | FailReason::ConnectionLost
        | FailReason::SignedOut
        | FailReason::Unreadable => {}
    }
}

fn every_readiness() -> Vec<Readiness> {
    let mut states = vec![
        Readiness::Selected,
        Readiness::Uploading,
        Readiness::Ready,
        Readiness::Removed,
        Readiness::Expired,
    ];
    states.extend(EVERY_REASON.map(|reason| Readiness::Failed { reason }));
    states
}

fn _every_state(state: Readiness) {
    match state {
        Readiness::Selected
        | Readiness::Uploading
        | Readiness::Ready
        | Readiness::Failed { .. }
        | Readiness::Removed
        | Readiness::Expired => {}
    }
}

fn sample(kind: Kind, original: &str) -> AttachmentRef {
    AttachmentRef {
        id: AttachmentId::parse("att_syn_0001").unwrap(),
        sha256: Sha256::parse("5a".repeat(32).as_str()).unwrap(),
        size_bytes: 10 * MIB,
        kind,
        name: SafeName::from_original(original),
        display_name: original.to_owned(),
    }
}

#[test]
fn ap11_schema_contracts_preserve_all_original_cases() {
    let cases: [(&str, fn()); 5] = [
        (
            "every_reference_the_core_serializes_matches",
            every_reference_the_core_serializes_matches,
        ),
        (
            "every_state_and_reason_the_core_serializes_is_in_the_schema",
            every_state_and_reason_the_core_serializes_is_in_the_schema,
        ),
        (
            "ids_and_hashes_are_checked_however_they_arrive",
            ids_and_hashes_are_checked_however_they_arrive,
        ),
        (
            "the_schema_uses_only_checked_keywords",
            the_schema_uses_only_checked_keywords,
        ),
        (
            "the_schemas_bounds_match_the_core",
            the_schemas_bounds_match_the_core,
        ),
    ];
    for (name, proof) in cases {
        eprintln!("TA2 case: ap11_schema::{name}");
        proof();
    }
}

fn the_schema_uses_only_checked_keywords() {
    let schema = attachment_schema();
    assert_eq!(schema["title"], ATTACHMENT_SCHEMA_ID);
    assert_eq!(ATTACHMENT_SCHEMA_ID, "openwiz.attachment.v1");
    assert_eq!(crate::pattern::lint(&schema), Vec::<String>::new());
    let errors = crate::pattern::validate(&schema, &json!({}));
    assert!(!errors.is_empty());
    assert!(
        errors.iter().all(|e| !e.contains("unresolvable")),
        "{errors:#?}"
    );
    for def in [
        "attachment",
        "attachment_id",
        "sha256",
        "kind",
        "safe_name",
        "readiness",
        "fail_reason",
    ] {
        assert!(schema["$defs"][def].is_object(), "{def}");
    }
}

fn every_reference_the_core_serializes_matches() {
    let schema = attachment_schema();
    for (kind, original) in [
        (Kind::Image, "synthetic.png"),
        (Kind::File, "Synthetic Report (final).pdf"),
        (Kind::File, "../../報告書\u{202e}.txt"),
        (Kind::File, ""),
    ] {
        let value = serde_json::to_value(sample(kind, original)).unwrap();
        let errors = crate::pattern::validate(&schema, &value);
        assert!(errors.is_empty(), "{original:?}: {errors:#?}");
        // And it reads back the same.
        let back: AttachmentRef = serde_json::from_value(value).unwrap();
        assert_eq!(back, sample(kind, original));
    }
    let longest = sample(Kind::File, &"a".repeat(500));
    assert_eq!(longest.name.as_str().len(), SAFE_NAME_MAX_BYTES);
    assert!(validate_def("attachment", &serde_json::to_value(longest).unwrap()).is_empty());
}

fn every_state_and_reason_the_core_serializes_is_in_the_schema() {
    for state in every_readiness() {
        let value = serde_json::to_value(state).unwrap();
        let errors = validate_def("readiness", &value);
        assert!(errors.is_empty(), "{value}: {errors:#?}");
        let back: Readiness = serde_json::from_value(value).unwrap();
        assert_eq!(back, state);
    }
    for reason in EVERY_REASON {
        let value = serde_json::to_value(reason).unwrap();
        assert!(validate_def("fail_reason", &value).is_empty(), "{value}");
        assert!(!reason.message().is_empty(), "{reason:?} has a reason");
    }
    let labels = attachment_schema()["$defs"]["fail_reason"]["enum"]
        .as_array()
        .cloned()
        .unwrap();
    assert_eq!(
        labels.len(),
        EVERY_REASON.len(),
        "no label without a reason"
    );
    for kind in [Kind::Image, Kind::File] {
        assert!(validate_def("kind", &serde_json::to_value(kind).unwrap()).is_empty());
    }
}

fn the_schemas_bounds_match_the_core() {
    let schema = attachment_schema();
    let defs = &schema["$defs"];
    assert_eq!(defs["safe_name"]["maxLength"], SAFE_NAME_MAX_BYTES as u64);
    assert_eq!(defs["safe_name"]["minLength"], 1);
    assert_eq!(
        defs["attachment_id"]["maxLength"],
        ATTACHMENT_ID_MAX_LEN as u64
    );
    assert_eq!(defs["sha256"]["minLength"], 64);
    assert_eq!(defs["sha256"]["maxLength"], 64);
    assert_eq!(defs["kind"]["enum"], json!(["image", "file"]));
}

fn ids_and_hashes_are_checked_however_they_arrive() {
    for good in ["att_syn_0001", "a", &"a".repeat(ATTACHMENT_ID_MAX_LEN)] {
        assert!(AttachmentId::parse(good).is_ok(), "{good}");
    }
    for bad in [
        "",
        "-a",
        "_a",
        ".",
        "..",
        "a/b",
        "a.b",
        "a b",
        &"a".repeat(ATTACHMENT_ID_MAX_LEN + 1),
    ] {
        assert!(AttachmentId::parse(bad).is_err(), "{bad:?}");
    }
    assert!(Sha256::parse(&"0123456789abcdef".repeat(4)).is_ok());
    for bad in [
        "",
        &"0".repeat(63),
        &"0".repeat(65),
        &"A".repeat(64),
        &"g".repeat(64),
    ] {
        assert!(Sha256::parse(bad).is_err(), "{bad:?}");
    }
    let mut value = serde_json::to_value(sample(Kind::File, "synthetic.txt")).unwrap();
    value["id"] = json!("../escape");
    assert!(serde_json::from_value::<AttachmentRef>(value.clone()).is_err());
    value["id"] = json!("att_syn_0001");
    value["sha256"] = json!("Z".repeat(64));
    assert!(serde_json::from_value::<AttachmentRef>(value).is_err());
}
