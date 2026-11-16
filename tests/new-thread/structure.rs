//! Structure: every label the core can serialize is in the schema.

use openwiz_core::messaging::send::UncertainReason;
use openwiz_core::new_thread::effects::EffectKind;
use openwiz_core::new_thread::options::{NoOptionsReason, UnavailableReason};
use openwiz_core::new_thread::outcome::{FailReason, RefusalReason, Status};
use serde_json::Value;

use crate::support::*;

macro_rules! labels {
    ($($item:expr),* $(,)?) => {
        vec![$(serde_json::to_value($item).unwrap()),*]
    };
}

#[test]
fn every_serialized_label_is_in_the_schema() {
    let schema = schema();
    let enums = |path: &str| -> Vec<Value> {
        schema
            .pointer(path)
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_else(|| panic!("no enum at {path}"))
    };
    let check = |path: &str, got: Vec<Value>| {
        let want = enums(path);
        for label in &got {
            assert!(want.contains(label), "{label} is not in {path}");
        }
        assert_eq!(want.len(), got.len(), "{path} lists only real labels");
    };
    check(
        "/$defs/refusal_reason/enum",
        labels![
            RefusalReason::NoOptions,
            RefusalReason::HarnessNotOffered,
            RefusalReason::ModelNotOffered,
            RefusalReason::EffortNotOffered,
            RefusalReason::ProjectNotFound,
            RefusalReason::ProjectAmbiguous,
            RefusalReason::ProjectPersonal,
            RefusalReason::ProjectNotStandard,
            RefusalReason::ProjectNoGithubRemote,
            RefusalReason::ProjectRemoteNotConfirmed,
            RefusalReason::ProviderUnsupported,
            RefusalReason::ProviderModelUnavailable,
            RefusalReason::ProviderEffortUnavailable,
            RefusalReason::ProviderMessageTooLong,
            RefusalReason::ProviderMessageEmpty,
            RefusalReason::ProviderProjectNotFound,
            RefusalReason::ProviderRequestIdConflict,
            RefusalReason::ProviderDiscoveryUnavailable,
        ],
    );
    check(
        "/$defs/fail_reason/enum",
        labels![
            FailReason::InterruptedBeforeDispatch,
            FailReason::ProjectsNotRead,
            FailReason::RecordNotWritten,
            FailReason::BudgetExhausted,
            FailReason::CallNotStarted,
        ],
    );
    check(
        "/$defs/uncertain_reason/enum",
        labels![
            UncertainReason::TimedOut,
            UncertainReason::EndedWithoutExitCode,
            UncertainReason::NotJson,
            UncertainReason::UnexpectedReceipt,
            UncertainReason::UndocumentedError,
            UncertainReason::CallNotConfirmed,
            UncertainReason::InterruptedAfterDispatchMark,
        ],
    );
    check(
        "/$defs/status/enum",
        labels![
            Status::Created,
            Status::Refused,
            Status::Failed,
            Status::Uncertain,
            Status::InProgress,
            Status::ConflictingReuse,
        ],
    );
    check(
        "/$defs/effect/properties/kind/enum",
        labels![
            EffectKind::CreatesAndStarts,
            EffectKind::StartsFromGithub,
            EffectKind::CopiesEnvFiles,
            EffectKind::FullPermissions,
            EffectKind::UsesCloudAgent,
            EffectKind::MacStaysAwake,
            EffectKind::CloudRoomNamesIt,
        ],
    );
    check(
        "/$defs/unavailable_harness/properties/reason/enum",
        labels![
            UnavailableReason::CatalogueNotReported,
            UnavailableReason::IdMappingNotVerified,
            UnavailableReason::NoOfferedEffort,
        ],
    );
    check(
        "/$defs/options/properties/state/oneOf/1/properties/reason/enum",
        labels![
            NoOptionsReason::NotReady,
            NoOptionsReason::HarnessesNotReported,
            NoOptionsReason::ReadFailed,
            NoOptionsReason::UnexpectedShape,
        ],
    );
}
