//! Spec 2's B4 (ClosedWiz#120): the start record's strict reader, which
//! `fleet tick --dry-run` uses, and archiving finished agents.
//!
//! Starting agents (`start_agent`) lost its last product caller with the
//! executing tick (#800), so its proofs went in CW2 (#1143).
//!
//! B4's files, declared from here: `fake` (the fakes), `record` (the start
//! record's strict reader) and `archive` (`thread archive`).
//!
//! **Fixtures only.** Fixture tests never prove live behaviour.

#[path = "b4_archive.rs"]
mod archive;
#[path = "b4_fake.rs"]
pub mod fake;
#[path = "b4_record.rs"]
mod record;
