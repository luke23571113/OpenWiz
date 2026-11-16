//! Foundation checks that pass in ticket 1: the approved dependency set, the
//! fixture scan, schema conformance and the pending list.
//! OpenWiz 0.0.5 (ClosedWiz#96) adds the skills folder's static check, and
//! ClosedWiz#170 the check that no test leaves a directory's mode to the umask.

#[path = "../support/schema.rs"]
mod schema;

#[allow(dead_code)]
#[path = "../support/dirs.rs"]
mod dirs;

mod ci_selection;
mod cockpit_schema_conformance;
mod dependencies;
mod dir_modes;
mod evidence_outside_crates;
mod fixture_scan;
mod pending;
mod plan_decisions_schema_conformance;
mod plan_links;
mod public_tree;
mod schema_conformance;
mod skills;

// The shared support's own proofs, run once here (#811).
#[allow(dead_code)]
#[path = "../support/forks.rs"]
mod forks;
#[allow(dead_code)]
#[path = "../support/place.rs"]
mod place;
#[path = "../support/real_time.rs"]
mod real_time;
mod support_proofs;

// LP1 contract conformance (ClosedWiz#543), using the existing extensions.
mod loops_schema;
#[path = "../new-thread/pattern.rs"]
mod pattern;
