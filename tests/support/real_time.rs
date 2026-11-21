//! Real-time proofs, in full or in their fast form (#1259, approved on the
//! ticket: option (a) of the builder's question, 2026-11-06).
//!
//! A few proofs must wait out real product limits (`RUN_BUDGET`,
//! `READ_TIMEOUT`), which no test can shorten. Each runs its fast form,
//! with the same logic assertions on shorter synthetic delays, only on the
//! first attempt of a pull request to `main` on GitHub Actions, read from
//! GitHub's own variables, each exactly. Everything else runs the full
//! real-time proof: a local run, a push to `main`, the nightly run, a rerun,
//! a pull request to `release-*`, a merge group, and any missing or odd
//! value. `OPENWIZ_TESTS_FULL`, set to anything, always selects the full
//! proofs.
//!
//! Its own tests are in `tests/checks/support_proofs.rs`, so they run once,
//! not once per target that includes this file (#811).

#![allow(
    dead_code,
    reason = "included by more than one test target, and each uses only part of it"
)]

use std::time::{Duration, Instant};

/// Which form a real-time proof runs in.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Form {
    /// The real-time proof, with the product's real limits.
    Full,
    /// The same logic on shorter synthetic delays: a first-attempt pull
    /// request to `main` only.
    Fast,
}

/// The form for this run, from the environment.
pub fn form() -> Form {
    form_in(&|name| std::env::var_os(name).map(|v| v.to_string_lossy().into_owned()))
}

/// The form for an environment given as a lookup, so the rule is tested.
pub fn form_in(var: &dyn Fn(&str) -> Option<String>) -> Form {
    if var("OPENWIZ_TESTS_FULL").is_some() {
        return Form::Full;
    }
    let is = |name: &str, want: &str| var(name).as_deref() == Some(want);
    if is("GITHUB_ACTIONS", "true")
        && is("GITHUB_EVENT_NAME", "pull_request")
        && is("GITHUB_BASE_REF", "main")
        && is("GITHUB_RUN_ATTEMPT", "1")
    {
        Form::Fast
    } else {
        Form::Full
    }
}

/// `full` for the full proof, else `fast`; says on stderr which ran.
pub fn pick<T>(proof: &str, full: T, fast: T) -> T {
    match form() {
        Form::Full => full,
        Form::Fast => {
            eprintln!(
                "{proof}: fast form on a first-attempt pull request to main; the \
                 real-time proof runs in full everywhere else (#1259)"
            );
            fast
        }
    }
}

/// How many times its measured ordinary read a scaled duration allows.
pub const SLACK: u32 = 4;

/// `nominal`, or `SLACK` times `measured` when that is longer, never above
/// `cap` (#2645).
pub fn scale(nominal: Duration, measured: Duration, cap: Duration) -> Duration {
    nominal.max(measured.saturating_mul(SLACK)).min(cap)
}

/// A deadline or timeout with room for this host's load (#2645). A proof
/// holds one read until `nominal` runs out, and its other reads must still
/// finish inside it. On a loaded runner they can take longer than a short
/// synthetic duration allows. `calibrate` runs one ordinary, unheld read of
/// the same kind first, and the result is [`scale`] of its wall time. The
/// held read still waits out the whole duration, so a 503, 504 or timeout
/// still means a real deadline miss. `cap` keeps the duration below the
/// product limit that would change the outcome.
pub fn scaled(proof: &str, nominal: Duration, cap: Duration, calibrate: impl FnOnce()) -> Duration {
    let started = Instant::now();
    calibrate();
    let measured = started.elapsed();
    let duration = scale(nominal, measured, cap);
    eprintln!(
        "{proof}: {duration:?} (nominal {nominal:?}, an ordinary read took {measured:?}, \
         slack x{SLACK}, cap {cap:?}; #2645)"
    );
    duration
}
