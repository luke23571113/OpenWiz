# #791 red run: cargo test --locked -p openwiz-tests --test cli-agent loop_export, before export is built (the stub answers not_built)

```text

running 5 tests
test loop_export::export_never_replaces_a_file_with_other_bytes ... FAILED
test loop_export::a_failed_loop_list_writes_nothing ... FAILED
test loop_export::export_reads_the_params_preamble_back_into_the_pinned_fixtures_checks ... FAILED
test loop_export::export_reports_each_loop_it_cannot_represent_and_writes_the_rest ... FAILED
test loop_export::export_writes_each_loop_of_the_project_complete_and_secret_free ... FAILED

failures:

---- loop_export::export_never_replaces_a_file_with_other_bytes stdout ----

thread 'loop_export::export_never_replaces_a_file_with_other_bytes' panicked at tests/cli-agent/loop_export.rs:100:5:
assertion `left == right` failed: stderr: 
  left: Some(5)
 right: Some(0)
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

---- loop_export::a_failed_loop_list_writes_nothing stdout ----

thread 'loop_export::a_failed_loop_list_writes_nothing' panicked at tests/cli-agent/loop_export.rs:100:5:
assertion `left == right` failed: stderr: 
  left: Some(5)
 right: Some(1)

---- loop_export::export_reads_the_params_preamble_back_into_the_pinned_fixtures_checks stdout ----

thread 'loop_export::export_reads_the_params_preamble_back_into_the_pinned_fixtures_checks' panicked at tests/cli-agent/loop_export.rs:100:5:
assertion `left == right` failed: stderr: 
  left: Some(5)
 right: Some(0)

---- loop_export::export_reports_each_loop_it_cannot_represent_and_writes_the_rest stdout ----

thread 'loop_export::export_reports_each_loop_it_cannot_represent_and_writes_the_rest' panicked at tests/cli-agent/loop_export.rs:121:5:
assertion `left == right` failed: {"command":"export","exit_code":5,"message":"openwiz loop export is not built yet; nothing was read or changed","schema":"openwiz.loop-not-built.v1","status":"not_built","ticket":791}
  left: ["$: missing required field project", "$: missing required field out", "$: missing required field loops", "$: unexpected field message", "$.schema: expected \"openwiz.loop-export.v1\", got \"openwiz.loop-not-built.v1\"", "$: unexpected field status", "$: unexpected field ticket"]
 right: []

---- loop_export::export_writes_each_loop_of_the_project_complete_and_secret_free stdout ----

thread 'loop_export::export_writes_each_loop_of_the_project_complete_and_secret_free' panicked at tests/cli-agent/loop_export.rs:100:5:
assertion `left == right` failed: stderr: 
  left: Some(5)
 right: Some(0)


failures:
    loop_export::a_failed_loop_list_writes_nothing
    loop_export::export_never_replaces_a_file_with_other_bytes
    loop_export::export_reads_the_params_preamble_back_into_the_pinned_fixtures_checks
    loop_export::export_reports_each_loop_it_cannot_represent_and_writes_the_rest
    loop_export::export_writes_each_loop_of_the_project_complete_and_secret_free

test result: FAILED. 0 passed; 5 failed; 0 ignored; 0 measured; 63 filtered out; finished in 1.99s

error: test failed, to rerun pass `-p openwiz-tests --test cli-agent`
```
