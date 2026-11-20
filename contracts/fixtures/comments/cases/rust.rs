// SPDX-License-Identifier: MIT
// Copyright 2030 Synthetic Example

use std::fmt;

// External: the synthetic vendor API rounds timeouts down to whole seconds, https://example.com/vendor/issues/7
const TIMEOUT_MS: u64 = 1000;

// SAFETY: the buffer outlives every reader.
static GREETING: &str = "hello // not a comment";

// Private record: https://github.com/jparker2006/ClosedWiz/issues/9001#issuecomment-9000000001
const RAW: &str = r#"/* still a string */"#;

// comment-ok: the synthetic linker needs this symbol name kept as written
pub fn kept() {}

// Loop over the items and add them up.
pub fn sum(items: &[u64]) -> u64 {
    items.iter().sum() // add them
}

/// Returns the answer.
pub fn answer() -> u64 {
    42
}

/* We tried a HashMap first but it was slower,
   so this stays a Vec. */
pub fn names() -> Vec<char> {
    vec!['a', '\'', '"']
}

// comment-ok:
pub fn bare() {}

// External: the platform needs this
pub fn linkless() {}

// let old = compute();
pub fn lifetime<'a>(s: &'a str) -> &'a str {
    s
}
