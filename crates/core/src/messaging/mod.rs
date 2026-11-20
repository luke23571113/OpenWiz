pub mod effects;
pub mod preview;
pub mod reconcile;
pub mod record;
pub mod send;
mod sha256;

use std::fmt;
use std::time::Duration;

use serde::{Deserialize, Serialize};

use crate::model::SessionId;

pub use sha256::{Sha256Hasher, sha256_hex};

pub const MESSAGING_SCHEMA_ID: &str = "openwiz.messaging.v1";

pub const RECORD_SCHEMA_ID: &str = "openwiz.send-record.v1";

pub const MAX_TEXT_BYTES: usize = 16 * 1024;

pub const OP_ID_MAX_LEN: usize = 64;

pub const SEND_BUDGET: Duration = Duration::from_secs(30);

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Mode {
    #[default]
    Queue,
    Steer,
}

impl Mode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Queue => "queue",
            Self::Steer => "steer",
        }
    }

    pub fn requested(self) -> &'static str {
        match self {
            Self::Queue => "Queue requested",
            Self::Steer => "Steer requested",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct OpId(String);

impl TryFrom<String> for OpId {
    type Error = InvalidRequest;

    fn try_from(id: String) -> Result<Self, Self::Error> {
        Self::parse(&id)
    }
}

impl From<OpId> for String {
    fn from(id: OpId) -> Self {
        id.0
    }
}

impl OpId {
    pub fn parse(id: &str) -> Result<Self, InvalidRequest> {
        let valid = !id.is_empty()
            && id.len() <= OP_ID_MAX_LEN
            && id.as_bytes()[0].is_ascii_alphanumeric()
            && id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-');
        if valid {
            Ok(Self(id.to_owned()))
        } else {
            Err(InvalidRequest(format!(
                "an op id is 1 to {OP_ID_MAX_LEN} ASCII letters, digits, _ or -, \
                 starting with a letter or digit"
            )))
        }
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for OpId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InvalidRequest(pub String);

impl fmt::Display for InvalidRequest {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

pub fn validate_text(text: &str) -> Result<(), InvalidRequest> {
    let refuse = |why: &str| Err(InvalidRequest(why.to_owned()));
    if text.is_empty() {
        return refuse("the text is empty");
    }
    if text.trim().is_empty() {
        return refuse("the text is only whitespace");
    }
    if text.contains('\0') {
        return refuse("the text contains a NUL character");
    }
    if text.len() > MAX_TEXT_BYTES {
        return Err(InvalidRequest(format!(
            "the text is {} bytes; the cap is {MAX_TEXT_BYTES} bytes of UTF-8",
            text.len()
        )));
    }
    Ok(())
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Binding {
    pub target: SessionId,
    pub mode: Mode,
    pub text_sha256: String,
    #[serde(
        default = "crate::prompt::empty_attachments_digest",
        skip_serializing_if = "is_empty_digest"
    )]
    pub attachments_digest: String,
}

fn is_empty_digest(digest: &str) -> bool {
    digest == crate::prompt::empty_attachments_digest()
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BindingField {
    Target,
    Mode,
    Text,
    Attachments,
}

impl Binding {
    pub fn new(target: SessionId, mode: Mode, text: &str) -> Self {
        Self {
            target,
            mode,
            text_sha256: sha256_hex(text.as_bytes()),
            attachments_digest: crate::prompt::empty_attachments_digest(),
        }
    }

    pub fn with_attachments(
        target: SessionId,
        mode: Mode,
        text: &str,
        attachments_digest: String,
    ) -> Self {
        Self {
            attachments_digest,
            ..Self::new(target, mode, text)
        }
    }

    pub fn differences(&self, other: &Binding) -> Vec<BindingField> {
        let mut differs = Vec::new();
        if self.target != other.target {
            differs.push(BindingField::Target);
        }
        if self.mode != other.mode {
            differs.push(BindingField::Mode);
        }
        if self.text_sha256 != other.text_sha256 {
            differs.push(BindingField::Text);
        }
        if self.attachments_digest != other.attachments_digest {
            differs.push(BindingField::Attachments);
        }
        differs
    }
}
