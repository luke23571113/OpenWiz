//! The attachment model's proof cases that need only `openwiz-core` (#14):
//! AP1 kind from bytes, AP2's limits, AP3 safe names, the readiness,
//! retention and free-disk rules, and the streaming SHA-256 staging hashes
//! with. Moved here from `tests/attachments` by #810; the cases that run
//! the store, the CLI or a child process stay there.
//!
//! **Fixtures only.** The synthetic bytes are built in memory at test time
//! (never committed), and fixture tests never prove CloudRoom's behaviour:
//! its limits and typing rules are source-read (#15's F4 to F7 and F26),
//! rechecked at the live check (AL2).

mod support;

mod ap01_kind;
mod ap02_limits;
mod ap03_safe_names;
mod rules;
mod sha256_stream;
