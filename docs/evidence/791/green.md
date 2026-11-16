# #791 green: scoped local checks at db65c591c8d9d1e69401804dc3404ebc68f33e7c (fresh round: R1, usage line)

```text
cli-agent: test result: ok. 70 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 29.53s
openwiz-cli --lib: test result: ok. 9 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
checks: test result: ok. 147 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 149.30s
service t6-update: test result: ok. 46 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 266.20s
cargo fmt --check: ok
cargo clippy -p openwiz-cli -p openwiz-tests --all-targets -- -D warnings: ok
cargo clippy --target aarch64-apple-darwin -p openwiz-cli --all-targets -- -D warnings: ok (type-check only)
cargo check --target aarch64-apple-darwin -p openwiz-tests --test cli-agent: ok, no warnings (type-check only)
```

The off-Linux tests are compiled for macOS but not run: CI is Linux only.
Earlier hand-backs: 616d9c9 (f6a4ea1) and 87625af (1afbd66), each with its full scoped set passing. CI runs the full suites.
