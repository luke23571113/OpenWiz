# #635 evidence: visibility-aware `openwiz init`

Fixture and recording proof only. Every repository, account, id and time is
synthetic; no real GitHub repository was read or created.

| Log | What failed first |
| --- | --- |
| `red-run.log` | The runtime proofs before `tools/install/setup/init.py` existed (can't open the runtime), the setup store refusing a `brain` field, and setup having no `check_brain`. |
| `red-store-reader.log` | The Rust setup-state reader refusing a valid companion brain reference. |
| `red-cli.log` | The installed CLI answering `unknown command init` and reaching no packaged runtime. |
| `red-p08a.log` | The P8(a) static proof refusing `crates/cli/src/init.rs` as a process start outside the permitted sources, before its recorded exception. |
| `red-packaging.log` | The installer accepting a bundle without `runtime/setup/init.py`, and the product collector not shipping it. |

Paths and temporary directories in the logs are replaced by `<repo>` and `<tmp>`.
No helpers were used.
