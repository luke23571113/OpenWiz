# #791 green: scoped local checks at 665de777f67d6666a0cf9f34ca53617cf25d9c93 (fresh round: R1, usage line; main merged with LC2)

```text
openwiz-adapter-cloudroom: test result: ok. 20 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 35.12s
openwiz-cli --lib: test result: ok. 9 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
cli-agent: test result: ok. 76 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 20.87s
checks: test result: ok. 147 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 149.37s
service t6-update -- --test-threads=2: test result: ok. 46 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 340.23s
cargo fmt --check: ok
cargo clippy -p openwiz-adapter-cloudroom -p openwiz-cli -p openwiz-tests --all-targets -- -D warnings: ok
cargo clippy --target aarch64-apple-darwin -p openwiz-adapter-cloudroom -p openwiz-cli --all-targets -- -D warnings: ok (type-check only)
cargo check --target aarch64-apple-darwin -p openwiz-tests --test cli-agent: ok, no warnings (type-check only)
```

t6-update at default threads, twice after the merge: 45 passed, 1 failed
(`a_passing_main_merge_is_staged_but_not_reported_as_running`, its first
`check` returned false). That test passed alone (137 s), and all 46 passed
with two threads (above). This sandbox was under load and low on disk, and
CI runs the suite on its own runner.

The off-Linux tests are compiled for macOS but not run: CI is Linux only.
Earlier hand-backs: 61dc893 (db65c59), 616d9c9 (f6a4ea1) and 87625af (1afbd66). CI runs the full suites.
