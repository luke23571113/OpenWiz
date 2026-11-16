# Loop CLI v1

LC1 of 0.0.17 (#789), spec #785. This is the shape that `openwiz loop
validate`, `export`, `plan` and `apply` are built against: their arguments,
their one JSON result each, their exit codes, the exact `room-cli loop`
command forms, and the plan's difference format. The result shapes are in
[`loop-cli.v1.schema.json`](loop-cli.v1.schema.json) (`$id`
`urn:openwiz:schema:loop-cli:v1`).

The loop file format is WizLoops', pinned byte for byte from
`openwizdev/WizLoops` commit `3847b375cbbf6ab0e88b0f643fa5a4e943183b03`
(the WL1 merge):

- [`wizloops-loop.v1.md`](wizloops-loop.v1.md), the format, and its schema
  [`wizloops-loop.v1.schema.json`](wizloops-loop.v1.schema.json);
- [`wizloops-cloudroom.v1.md`](wizloops-cloudroom.v1.md), the Cloudroom
  adapter rules;
- [`fixtures/wizloops/`](fixtures/wizloops/), the format's fixtures, with
  the [pin record](fixtures/wizloops/README.md).

Where this contract and the pinned format or adapter rules differ, the pinned
files hold. This contract adds only what WizLoops leaves to OpenWiz: the
arguments, results, exits and the binding syntax. `secrets: "all"` is part of
the format (a loop that gets every secret), valid outside a catalog.

**Implementation boundary.** LC1 ships the four commands as stubs. Each one
parses its arguments as below, then refuses with the `not_built` result,
reads nothing and changes nothing. LC2 (#790) builds `validate`, LC3 (#791)
`export`, LC4 (#792) `plan`, and LC5 (#793) `apply`. Each of those tickets
replaces its own stub, its catalogue entry and its row below. No section here
makes a command available before its ticket ships it, and no fixture proves
live behaviour. Nothing here touches the earlier loop scheduler or
`openwiz loop off|on` ([loops.v1.md](loops.v1.md)).

## Arguments

```text
openwiz loop validate <path>... [--catalog] [--json]
openwiz loop export --project <project> [--out <dir>] [--json]
openwiz loop plan <path>... --project <project> [--adopt <id>=<loop>]... [--json]
openwiz loop apply <id> --project <project> [--file <path>] [--adopt <id>=<loop>] [--json]
openwiz loop <command> --help|-h [--json]
```

- **Order.** Options and operands may come in any order after the command
  word. `--` ends the options: every later token is an operand, even one
  that starts with `-`.
- **Values.** A value option takes the next token as its value. `=value` is
  refused. A value that is empty, contains a control character or starts
  with `-` is refused, so `--json` is never a value.
- **Once.** Each option appears at most once, except `--adopt` in `plan`,
  which may repeat. A form that is not listed (`export` with an operand,
  `apply` with two ids, `validate --project`) is refused.
- **`<path>`.** A loop file, or a folder read as the format's "Folders"
  says. At least one is required for `validate` and `plan`.
- **`--catalog`.** `validate` reads every folder as a catalog (the format's
  "Catalogs").
- **`--project <project>`.** The Cloudroom project whose loops are read and
  changed. `room-cli loop list` returns every loop on the account, and the
  adapter reads only the loops with this `project_id`. It is required for
  `export`, `plan` and `apply`: there is no default.
- **`--out <dir>`.** Where `export` writes its files; default the current
  directory. Export writes `<id>.md` for each loop, and `<id>/check` for
  each loop with a script. A file that already exists with other bytes is
  never replaced: that loop is refused with `export-exists`.
- **`<id>` and `--file <path>`.** `apply` changes the one loop with this
  loop file `id`, from the file `--file` names, default `./<id>.md`. A file
  whose `id` is not `<id>` is refused with `apply-id-mismatch`.
- **`--adopt <id>=<loop>`.** The adapter's binding (its "Adopting an
  unmarked loop"): the loop file `id` before the first `=`, the Cloudroom
  loop id after it. A binding is given for one run and never stored.
- **`--json`.** Selects JSON. Like every `openwiz` command, it is chosen from
  the option tokens before `--` ([cli.v1.md](cli.v1.md#json-selection-and-streams-t2-runtime)).
- **Help.** `--help` or `-h` before `--` prints the loop commands' usage and
  exits 0, wrapped in `openwiz.cli-help.v1` with `--json`. It reads nothing.
- An argument that is not UTF-8 is refused.

A refused form exits 2 and reads nothing. With `--json` it prints one
`openwiz.cli-error.v1` document whose `command` is the form's name
(`loop.validate`, `loop.export`, `loop.plan` or `loop.apply`) and whose
`error.kind` is `usage`.

## Results

Without `--json`, output is for people and may change. With `--json`, every
run prints exactly one document and a newline on stdout, and nothing else on
stdout. Each document has `schema`, `command` and `exit_code`, and the
`exit_code` is the process's exit code.

| Command | Document (`loop-cli.v1.schema.json#/$defs/…`) | Shipped by |
| --- | --- | --- |
| any, before its ticket ships | `openwiz.loop-not-built.v1` (`not_built`) | LC1 |
| `validate` | `openwiz.loop-validate.v1` (`validate_report`) | LC2 |
| `export` | `openwiz.loop-export.v1` (`export_report`) | LC3 |
| `plan` | `openwiz.loop-plan.v1` (`plan_report`) | LC4 |
| `apply` | `openwiz.loop-apply.v1` (`apply_report`) | LC5 |

A usage error, or a failure before any result exists (an unreadable path,
a failed `loop list`), uses `openwiz.cli-error.v1` instead, as
[cli.v1.md](cli.v1.md) says.

**A refusal** is `{"file", "code", "field", "message"}`. `code`, `field`
and `message` are the format's or the adapter's, exactly as their refusal
tables write them, or one of OpenWiz's own codes below. `file` is the loop
file's path as given (inside a folder: the folder's path, then `/` and the
file name). For a refusal of a Cloudroom loop during export, `file` is the
Cloudroom loop's `name`. A text run prints each one as
`<file>: <field>: <message>`, the format's line form.

OpenWiz's own codes:

| Code | Field | Message |
| --- | --- | --- |
| `export-exists` | `file` | `<path> already exists with other bytes; nothing was written for this loop` |
| `apply-id-mismatch` | `id` | `the file's id is <file id>, not <id>` |
| `loop-started-thread` | `file` | `apply runs only from an ordinary thread or a terminal, never a thread a loop started` |

**`not_built`** (LC1): `{"schema": "openwiz.loop-not-built.v1",
"command": "<validate|export|plan|apply>", "exit_code": 5, "status":
"not_built", "ticket": <790|791|792|793>, "message": "openwiz loop <command>
is not built yet; nothing was read or changed"}`. Text: one line on stderr,
`openwiz: loop <command> is not built yet (#<ticket>); nothing was read or
changed`, and nothing on stdout.

**`validate_report`**: `files`, one entry per loop file read, in the order
given (a folder's files in byte order of name): `file`, `id` (the parsed
`id`, or null when it has none), `result` (`valid` or `refused`) and
`refusals` (in the format's report order). Then `folder_refusals`, the
folder and catalog refusals (`duplicate-id`, `catalog-all-secrets`), in the
format's order. A file passes or fails exactly as the pinned fixtures'
`expected.json` says.

**`export_report`**: `project`, `out`, and `loops`, one entry per loop of
the project in `loop list` order: `loop` (the Cloudroom id), `id` (the
file's id, or null when refused before one exists), `result` (`written`,
`unchanged` when identical files already exist, or `refused`), `files` (the
paths written or found unchanged, relative to `out`), `binding` (for an
unmarked loop, `{"id", "loop"}`, the `--adopt` it needs; otherwise null)
and `refusals`. Export never writes a webhook address or a secret's value:
`loop list` holds neither, and only `list`'s mapped keys reach a file.

**`plan_report`**: `project`, and `items`, one per loop file in the order
read: `file`, `id`, `action` (`create`, `update`, `none` or `refused`),
`loop` (the managed or bound Cloudroom id, or null), `paused` (the managed
loop has `enabled: false`), `commands` (the exact command forms, below:
none for `none` and `refused`), `differences` (below), `refusals` and
`notes` (the adapter's reported limits, such as a same-thread run keeping
its thread's environment). Then `unmanaged` (`{"loop", "name"}` for each
loop of the project with no marker and no binding) and `orphans`
(`{"loop", "id"}` for each managed loop with no file). Plan reads only
`loop list` and changes nothing.

**`apply_report`**: `project`, `id`, `file`, `action` (as in plan),
`loop`, `commands` (exactly the plan's commands for this id), `outcome`,
`read_back` and `refusals`.

- `outcome` is `created`, `updated` or `unchanged` when Cloudroom accepted
  every command and the read-back shows no difference; `different` when it
  accepted them and the read-back shows a difference; `refused` when
  nothing was written; `failed` when Cloudroom refused a command (its
  message is in `refusals` with code `room-cli`, field `file`, unchanged);
  and `unknown` when an outcome is unclear (no exit code, a timeout, a
  `list` that fails after a write). An unknown outcome is never retried.
- `read_back` is null when nothing was written, otherwise
  `{"differences": [...]}` from one `loop list` after the last command,
  compared as plan compares.
- `webhook_address` appears only for a created webhook loop: `create`'s
  address, passed to the caller this once. Apply writes it to no file, plan
  or log.

## Exit codes

The values are [cli.v1.md](cli.v1.md#fixed-exits-and-existing-results)'s.

| Exit | `validate` | `export` | `plan` | `apply` |
| --- | --- | --- | --- | --- |
| 0 | every file valid | every loop written or unchanged | printed, no refusal (differences are fine) | `created`, `updated` or `unchanged` |
| 1 | a path unreadable; output failed | `loop list` failed; output failed | a path unreadable; `loop list` failed; output failed | a read before any write failed; output failed |
| 2 | usage | usage | usage | usage |
| 5 | a file or folder refused; `not_built` | a loop refused (the others are still written); `not_built` | a file refused (the others are still planned); `not_built` | `refused`, `failed` or `different`; `not_built` |
| 6 | | | | `unknown` |

## `room-cli loop` command forms

Every call goes through the adapter's allowlist
(`crates/adapters/cloudroom/src/allowlist.rs`). The read is already there.
`create` and `update` join it only with Jake's approval, which LC5 asks for
before any write. The forms come from `room-cli loop --help` (cloudroom
0.1.111); a live call has not been observed.

| Use | Exact form, after `room-cli` |
| --- | --- |
| Read every loop (export, plan, apply's read-back) | `loop list --json` |
| Create | `loop create --name <name> --prompt-file <path> <trigger> --new-thread\|--same-thread [--script-file <path>] [--provider <p> --model <m> --reasoning <r>] --priority <n> --secrets <secrets>` |
| Update | `loop update <loop> [--name <name>] [--priority <n>] [--prompt <text>] [--cron <cron> --timezone <zone> \| --at <time>] [--script-file <path>] [--provider <p> --model <m> --reasoning <r>] [--secrets <secrets>]` |

- `<trigger>` is `--cron <cron> --timezone <zone>`, `--at <time>`, `--in
  <delay>` or `--webhook`. Every value is the adapter's mapping ("A file to
  `room-cli loop create`" and "to `room-cli loop update`"), in its flag
  order. `update` carries only the flags for fields that differ.
- `loop list --json` prints `{"automations": [...]}`, each item with the
  keys the adapter maps. It is the existing T5 read, unchanged.
- **Files.** `--prompt-file` and `--script-file` name files that `apply`
  writes, owner-only, in a private temporary folder it removes afterwards.
  They hold the body and the check script with params replaced, byte for
  byte.
- **Never called:** `loop pause`, `resume`, `run`, `delete`, `hook` and
  `report`. There is no `loop show`: a loop is read back only through
  `loop list`.

**A command in a result** is `{"argv": [...], "files": {...}}`. `argv` is
the arguments after `room-cli`. Each file operand is written as `@prompt`
or `@script`, and `files` maps each of those to the text the file holds. A
text run prints the command as `room-cli` and each argument quoted for
`sh`, then each file's text. Example, `contracts/fixtures/wizloops/valid/at-same.md`
created:

```json
{"argv": ["loop", "create", "--name", "One reminder [wizloop:at-same]", "--prompt-file", "@prompt", "--at", "2030-01-02T03:04:05Z", "--same-thread", "--priority", "3", "--secrets", "none"], "files": {"@prompt": "Remind the owner to read the example report.\n"}}
```

## The difference format

A difference is `{"field", "file", "live"}`. `field` is one of `name`,
`trigger`, `thread`, `agent`, `priority`, `secrets`, `body` and `check`,
in that order. `file` is the value the file maps to and `live` the value
the managed loop maps back to, both as JSON in the loop file's shape (as
the adapter's "How plan compares" reads them):

- `name`: the name without its marker.
- `trigger`: the whole trigger object.
- `agent`: the agent object, or null for the caller's agent.
- `secrets`: `"all"`, or the list. A list compares as a set, and is shown
  in its own order.
- `body`, `check`: the text after params are replaced, or null for no
  check. An `at` time compares as an instant, so a different spelling of
  the same instant is no difference.

An item with no difference has `"differences": []`. A text run prints each
difference as `<file>: <field>: <live> -> <file value>`, with each value
as compact JSON.

Example: a managed loop whose priority is 3 while its file says 2:

```json
{"field": "priority", "file": 2, "live": 3}
```

## The fake `room-cli`

`tests/fake-room-cli/` answers `loop list --json`, `loop create` and
`loop update` from a scenario, as for every other call. Its synthetic
`loops/` scenario has one project's loops: a marked cron loop with a
check, an agent and named secrets; a webhook loop; a loop with every secret
(`secrets: null`); a paused same-thread `at` loop; an unmarked loop; and a
loop in another project. The fake refuses any other `loop` form, including
`show`, as off the allowlist (exit 97). It records each `create` and
`update`, with its arguments and the bytes of each named file, as one JSON
line in `loop-writes.log`. A test that expects no write checks that the log
does not exist.
