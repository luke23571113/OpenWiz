//! What remains of the health planner after the service's health checks,
//! repairs and takeover were retired (0.0.17): the ids and repository rule the
//! kept CloudRoom loop inventory and the Decisions page use, the one rule for
//! which loops are OpenWiz's, and how long a subject stays healthy.
//!
//! [`model`] holds the types, and [`is_openwiz_loop`] the loop rule.

pub mod model;

use model::Repository;

/// How long a subject stays healthy before its incident ends: an hour.
pub const HEALTHY_FOR_MS: i64 = 3_600_000;

/// The start every OpenWiz loop's name has: `launch-fleet` and a space.
const LOOP_PREFIX: &str = "launch-fleet ";

/// Whether a loop named `name` is one of OpenWiz's: the name starts
/// `launch-fleet ` and, split at each space, has the repository
/// (`<owner>/<name>`) as one of its words, compared exactly.
pub fn is_openwiz_loop(name: &str, repository: &Repository) -> bool {
    let word = repository.to_string();
    name.starts_with(LOOP_PREFIX) && name.split(' ').any(|w| w == word)
}
