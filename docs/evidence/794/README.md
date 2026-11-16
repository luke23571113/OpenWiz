# LC6 (#794): live read-only proof of export and plan — public summary

The live files and outputs are private: the exported loop files, both `loop list` snapshots, and the export and plan JSON hold real prompts, names and ids. They are in the private repository.
Private record: https://github.com/jparker2006/ClosedWiz/pull/3039#issuecomment-6931951031

This page holds only counts and the result.

## How it ran (2026-11-16)

- **Live calls:** `room-cli loop list`, twice (before and after), in the builder's cloud sandbox. Nothing else ran against the account: no apply, create, update, pause, resume, run, delete or hook.
- **The shipped binary** (`openwiz loop export`, built from `main` after #980) exited 1 before it ran anything. It never runs a `room-cli` found on `PATH`, and the sandbox has no bundled CloudRoom launcher.
- **Export and plan** ran through the test-only fixture entrypoint (`tests/fixture-entrypoints/cli.rs`). The fixture's program is a replay script: it answers only `loop list --json`, from the first snapshot, and refuses every other form. It recorded only `loop list --json` calls. The export and plan code is the shipped code. Launcher discovery is the only part this run did not exercise.

## Counts

| What | Count |
| --- | --- |
| Loops on the account | 162 |
| Enabled loops (all in one project; the ticket expected 20) | 21 |
| Loops in that project | 153 |
| Export: written / refused / with unmapped keys | 152 / 1 / 0 |
| Enabled loops written | 21 of 21 |
| Refused: one disabled loop whose check uses a `{{…}}` placeholder (`cf-export-invalid` on `check`, the format's `param-in-check`) | 1 |
| Plan on the 21 enabled files, with export's `--adopt` bindings: exit / differences / refusals | 0 / 0 / 0 |
| Plan on all 152 written files: exit / differences / refusals | 0 / 0 / 0 |
| Commands plan would run: the adapter's adoption rename (`loop update <loop> --name`, adding the marker), one per file | 21 (enabled) |
| Loops whose settings changed between the two reads (run times excluded) | 0 |

## Result

Export and plan agree on the live loops. Plan shows no difference for any enabled loop. Nothing was applied and nothing changed on the account. No bug was found in export or plan, so no fixture issue was filed.

## Helpers

None. The builder did all the work in one session, so there was no swarm and no no-push check.
