# #1044 / #1060: the staged program kept busy by a concurrent fork

Synthetic fixtures only. Paths are replaced by `<synthetic-fixture>`.

## Cause

`crates/service/src/update.rs::copy_file` wrote the staged candidate program in
the multithreaded service process. A child another thread forked during that
copy kept the writable descriptor until its own exec. The identity call
(`openwiz-service --update-build`) then failed with ETXTBSY, and the update was
kept on the old build at step `build`. The #1046 builder measured this with the
preload probe below and a same-artifact control (see #1060).

## Proof

`t6_update::a_passing_main_merge_is_staged_but_not_reported_as_running` now
runs with `fixture::Inheritor` watching the staged program. The moment this
process holds a writer for it, a child takes a writer for the same file and
keeps it until the check returns, as a child forked then would have.

- `red.log`: before the fix. The identity call fails and the update is not
  staged (`assertion failed: f.updater(&old).check(&state, 1000).unwrap()`).
- `green.log`: after the fix, the same test stages the candidate.
- `green-probe.log`: after the fix, the same test under the #1046 probe
  (`inherited-writer.c`, `OW_UPDATE_KEEP_WRITER=1`, preloaded into the test
  binary). It passes, and the probe never fires: the service no longer closes a
  writer for the candidate, because it never opens one.
- `green-t6-update.log`: the whole `t6-update` binary at the fix.

Commands:

```sh
cargo test -p openwiz-service --test t6-update a_passing_main_merge_is_staged_but_not_reported_as_running -- --exact --nocapture --test-threads=1
cc -shared -fPIC -Wall -Wextra -Werror docs/evidence/1044/inherited-writer.c -ldl -o /tmp/inherited-writer.so
OW_UPDATE_KEEP_WRITER=1 LD_PRELOAD=/tmp/inherited-writer.so target/debug/deps/t6_update-<hash> --exact a_passing_main_merge_is_staged_but_not_reported_as_running --nocapture --test-threads=1
```

The staging safeguards are a table in
`t6_update::staging_refuses_a_planted_target_a_symlinked_program_or_another_identity`.
Two mutations were run by hand against it and both failed it: `rename` in place
of `hard_link` (a planted path replaced), and `metadata` in place of
`symlink_metadata` (a symlinked build output staged).
