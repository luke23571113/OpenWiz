pub mod effects;
pub mod operation;
pub mod options;
pub mod outcome;
pub mod read;
pub mod record;
pub mod start;
pub mod status;

use std::time::Duration;

use serde::Serialize;

use crate::messaging::{InvalidRequest, OpId, sha256_hex};
use crate::prompt::PromptPayload;

pub const NEW_THREAD_SCHEMA_ID: &str = "openwiz.new-thread.v1";

pub const RECORD_SCHEMA_ID: &str = "openwiz.new-thread-record.v1";

pub const STATUS_SCHEMA_ID: &str = "openwiz.new-thread-status.v1";

pub const OPTIONS_SCHEMA_ID: &str = "openwiz.cloud-options.v1";

pub const NEW_THREAD_BUDGET: Duration = Duration::from_secs(30);

pub const SETTING_MAX_LEN: usize = 128;

pub const REQUEST_ID_PREFIX: &str = "ow1-";

pub const REQUEST_ID_DOMAIN: &str = "openwiz.new-thread.request-id.v1:";

pub fn request_id(op_id: &OpId) -> String {
    let digest = sha256_hex(format!("{REQUEST_ID_DOMAIN}{op_id}").as_bytes());
    format!("{REQUEST_ID_PREFIX}{}", &digest[..40])
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", content = "value", rename_all = "snake_case")]
pub enum ProjectRef {
    Id(String),
    Name(String),
}

impl ProjectRef {
    pub fn as_str(&self) -> &str {
        match self {
            Self::Id(s) | Self::Name(s) => s,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Settings {
    pub harness: String,
    pub model: String,
    pub effort: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NewThreadRequest {
    pub project: ProjectRef,
    pub settings: Settings,
    pub prompt: PromptPayload,
    pub op_id: OpId,
    pub budget: Duration,
}

impl NewThreadRequest {
    pub fn new(
        project: ProjectRef,
        settings: Settings,
        prompt: PromptPayload,
        op_id: OpId,
    ) -> Self {
        Self {
            project,
            settings,
            prompt,
            op_id,
            budget: NEW_THREAD_BUDGET,
        }
    }

    pub fn validate(&self) -> Result<(), InvalidRequest> {
        self.prompt.validate()?;
        if self.project.as_str().trim().is_empty() {
            return Err(InvalidRequest("the project is empty".to_owned()));
        }
        if self.project.as_str().contains('\0') {
            return Err(InvalidRequest(
                "the project contains a NUL character".to_owned(),
            ));
        }
        for (name, value) in [
            ("harness", &self.settings.harness),
            ("model", &self.settings.model),
            ("effort", &self.settings.effort),
        ] {
            check_setting(name, value)?;
        }
        Ok(())
    }
}

fn check_setting(name: &str, value: &str) -> Result<(), InvalidRequest> {
    if value.is_empty() {
        return Err(InvalidRequest(format!(
            "the {name} is not given; nothing is defaulted"
        )));
    }
    let valid = value.len() <= SETTING_MAX_LEN
        && !value.starts_with('-')
        && value.bytes().all(|b| b.is_ascii_graphic());
    if valid {
        Ok(())
    } else {
        Err(InvalidRequest(format!(
            "the {name} is 1 to {SETTING_MAX_LEN} printable ASCII characters, with no space and \
             not starting with -"
        )))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Binding {
    pub project: ProjectRef,
    pub harness: String,
    pub model: String,
    pub effort: String,
    pub text_sha256: String,
    pub attachments_digest: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum BindingField {
    Project,
    Harness,
    Model,
    Effort,
    Text,
    Attachments,
}

impl BindingField {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Project => "project",
            Self::Harness => "harness",
            Self::Model => "model",
            Self::Effort => "effort",
            Self::Text => "text",
            Self::Attachments => "attachments",
        }
    }
}

impl Binding {
    pub fn new(request: &NewThreadRequest, attachments_digest: String) -> Self {
        Self {
            project: request.project.clone(),
            harness: request.settings.harness.clone(),
            model: request.settings.model.clone(),
            effort: request.settings.effort.clone(),
            text_sha256: request.prompt.text_sha256(),
            attachments_digest,
        }
    }

    pub fn differences(&self, other: &Binding) -> Vec<BindingField> {
        [
            (BindingField::Project, self.project == other.project),
            (BindingField::Harness, self.harness == other.harness),
            (BindingField::Model, self.model == other.model),
            (BindingField::Effort, self.effort == other.effort),
            (BindingField::Text, self.text_sha256 == other.text_sha256),
            (
                BindingField::Attachments,
                self.attachments_digest == other.attachments_digest,
            ),
        ]
        .into_iter()
        .filter(|(_, same)| !same)
        .map(|(field, _)| field)
        .collect()
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ProjectView {
    pub id: String,
    pub name: crate::model::Fact<String>,
}
