//! The kept OpenWiz 0.0.4 new-thread proof cases (ClosedWiz#11), each
//! written before the behaviour: the ones that run the core's new-thread
//! rules, which the fleet engine starts agents through. `openwiz new` and
//! `openwiz models`, and their cases, went in #1264.
//!
//! **Fixtures only.** The proofs run the core against an in-memory record
//! store and a fake client that answers through the adapter's own parsers.
//! Nothing is created live, and fixture tests never prove live behaviour.
//!
//! `contract_tables` checks the contracts' good and bad JSON (`pattern` is
//! its schema checker). The project names moved to
//! `crates/core/tests/` (#808).

mod support;

#[allow(
    dead_code,
    reason = "shared with other test targets; this one uses only part of it"
)]
#[path = "../support/schema.rs"]
mod schema;

#[path = "../support/dirs.rs"]
mod dirs;

// Waiting out a forked child's copy of a file (#176).
#[allow(
    dead_code,
    reason = "shared with other test targets; this one uses only part of it"
)]
#[path = "../support/forks.rs"]
mod forks;

// Reading the fake's call counters (#176).
#[allow(
    dead_code,
    reason = "shared with other test targets; this one uses only part of it"
)]
#[path = "../support/counter.rs"]
mod counter;

mod contract_tables;
mod n04_offered_only;
mod n05_honest_options;
mod n06_outcome_mapping;
mod n07_requested_and_reported;
mod n08_start_stages;
mod n11_op_id_binding;
mod n14_prompt_seam;
mod n16_allowlist;
mod n17_drift;
mod n18_report;
mod n19_status_read_only;
mod pattern;
