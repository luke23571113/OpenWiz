# #791 green: scoped local checks at f6a4ea10357fd5f9a03f59c3ada58f0aea7a78a1 (review round: R1 and R2)

```text
cli-agent: test result: ok. 70 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 26.89s
openwiz-cli --lib: test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
openwiz-adapter-cloudroom: test result: ok. 18 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 35.17s
messaging m12: test result: ok. 8 passed; 0 failed; 0 ignored; 0 measured; 181 filtered out; finished in 0.23s
attachments ap10: test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 64 filtered out; finished in 0.00s
checks: test result: ok. 147 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 187.84s
service t6-update: test result: ok. 46 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 279.44s
cargo fmt --check: ok
cargo clippy -p openwiz-adapter-cloudroom -p openwiz-cli -p openwiz-tests --all-targets -- -D warnings: ok
```

Earlier hand-back: 1afbd66485ca97a1e1e5909b4098b10c7ec02658 (same set, all passed). CI runs the full suites.
