# #791 green: scoped local checks at 1afbd66485ca97a1e1e5909b4098b10c7ec02658

```text
cli-agent: test result: ok. 69 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 24.02s
openwiz-cli --lib: test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
openwiz-adapter-cloudroom: test result: ok. 18 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 35.11s
messaging m12: test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 181 filtered out; finished in 0.23s
attachments ap10: test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 64 filtered out; finished in 0.00s
checks: test result: ok. 147 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 178.67s
service t6-update: test result: ok. 46 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 266.57s
cargo fmt --check: ok
cargo clippy -p openwiz-adapter-cloudroom -p openwiz-cli -p openwiz-tests --all-targets -- -D warnings: ok
```

CI runs the full suites.
