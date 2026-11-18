# WizRoom v1 (`openwiz.wizroom.v1`)

Contract-first boundary for spec #979, ticket WM1 (#1056): the war room moves
from OpenWiz's `tools/war-room/` into its own private repository,
`openwizdev/WizRoom`. This contract pins the rule that splits the folder, the
names and forms the later tickets (WM2 to WM10) build to, and the cut-over
order. It implements nothing but the offline split checker, and it activates
nothing: no repository setting, workflow, variable, secret, branch, runner or
machine unit changes because of it.

Authority: Jake, 2026-11-16: the war room moves into its own private
repository, WizRoom; the measurement spec's in-flight war-room work lands
first, then everything moves in one go
([private record](https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-6912815852)).
This contract relies on [open development v1](open-development.v1.md). Approving
spec #979's plan is **not** the go for the cut-over or for either removal; each
runs only on its own recorded go.

Words: the **folder** is `tools/war-room/` in OpenWiz. **The private record** is
the private development repository that publishes the war room today. **The
machine** is the owner's machine that serves the war room. This contract names
no address, machine, account, sample or private-record content.

## The split rule

A file in the folder **stays public** if a public OpenWiz file outside the
folder reaches it, by one of:

1. **an import**: a Python `import`, `from … import`, `importlib.import_module`
   or `__import__` (by position or `name=`) that resolves to it, through the
   importing file's own folder or a `sys.path` entry the file adds, in regular
   and namespace packages (a directory without `__init__.py`); at module
   level, Python's search order applies (entries added above the import, first
   match wins); inside a function, any entry the file adds counts;
2. **a native load**: a load by file path, such as Python's
   `importlib.util.spec_from_file_location`, `SourceFileLoader`,
   `runpy.run_path` or `exec(open(…))` (by position or keyword, and under any
   name the file imports it as), a shell `.`/`source`, or a JavaScript
   `require`, `import(…)` or static `import … from`, on one line or across
   several (never inside a comment or a string);
3. **an executable dependency**: a script invoked by a public script, a
   workflow's `run` command or a loop's `argv`; or a runtime file path that
   code reads, including Python paths computed from `__file__` and literals
   (`Path(…)`, `/`, `parent`, `parents[n]`, `os.path.join`, `joinpath`,
   `with_name`).

A path that names a directory in the folder reaches every file under it. The
bare folder path alone reaches nothing by itself; a `sys.path` entry naming it
makes imports resolve there.

**Files reached from those count too**: every staying file's executable
dependencies keep their targets public. Prose links, fixture logs, comments
and test-only synthetic path strings do not retain a file. A test travels
with the code it tests. Documentation links are updated to the new public
location or name the private repository. **Everything else moves.**

**Which public files count.** A file outside the folder counts when it is:

| Class | Files | Kind in the report |
| --- | --- | --- |
| script | a `.py`, `.sh`, `.bash`, `.zsh`, `.mjs`, `.cjs`, `.js`, `.ts` or `.rs` file, or any file starting with `#!` | `script path` |
| workflow | `.github/workflows/*.yml` or `*.yaml`, and `.github/actions/**/action.yml` | `workflow path` |
| loop | `loops/**/*.json` | `loop path` |

Imports and native loads report as `import` and `native load`. Only executable
references in the listed classes retain files, not a path merely written in
one of those files. Prose, logs, registries, workflow path filters and other
data never keep a file public; their mentions are corrected by the ticket
that moves the file.

Two sets of files outside the folder are **not public consumers**:

- **The war room's own files outside the folder**, which leave with it:
  `.github/workflows/war-room.yml` and `.github/workflows/war-room-proof.yml`.
  They publish and test the war room itself; counting them would keep the whole
  folder public. WizRoom's own CI and publishing workflow (WM3, WM4) replace
  them, and WM9 removes them.
- **The checker's synthetic trees**, `ci/wizroom/fixtures/`: test data with
  their own synthetic `tools/war-room/` folders, never consumers of the real one.

**Resolving and refusing.** References are resolved from the tree alone. A
Python path is evaluated from `__file__`, string literals, module-level and
local assignments, conditional expressions (each branch), literal `for` loops
over string tuples or lists, and, when a load's path comes from a function
parameter, every call of that function (or, for a method, of
`<object>.<method>`) in the same file. A JavaScript load is evaluated from
string literals, templates, `+`, a constant assigned once in the file,
`String(…)`, and `new URL(<path>, import.meta.url)` or such a URL.

A **load** (an import's search path, a module name, or a native load) that
cannot be fully resolved is **refused, with its file and line**, unless its
known parts rule out every file in the folder. Whether the file mentions the
folder is no evidence either way: a wholly computed load (`. "$PLUGIN"`,
`require(name)`, `sys.path.insert(0, os.environ[…])`) is refused unless it is a
listed [caller-supplied load site](#caller-supplied-loads). A computed piece of
a file path may hold `..`, so only the known text after its
first computed piece can rule a folder file out (`require('./plugins/' + name
+ '.json')` passes when the folder holds no `.json` file). A computed search
path is refused when it could be the folder, a directory in it or a directory
above it. A computed module name is refused when, through the file's own folder
or any `sys.path` entry it adds, it could name a module in the folder. A partly
computed plain path (not a load) counts only when its known part names the
folder's own segment (`war-room/`), and then every folder file it can match
stays. An unreadable file is refused too. A refusal is fixed by making the
reference resolvable, never by weakening the rule.

## The split checker

`ci/wizroom/split.py` applies the rule. It is offline and read-only: it reads a
repository tree (its tracked files when the tree is a Git checkout, otherwise
every file under it), **writes nothing and makes no network call**.

```sh
python3 -I ci/wizroom/split.py --root <tree> [--folder tools/war-room] [--own <path>]...
```

`--own` replaces the default list of the war room's own outside files (above).
On success it prints, sorted, one line per folder file, then a total, and exits
**0**:

```text
stay tools/war-room/<file> <- <referring file>:<line> <kind>
move tools/war-room/<file>
total: <n> stay, <m> move
```

Each staying file names the first reference that keeps it public, in a
breadth-first walk from the public files in path order. On any refusal it
prints no stay or move set, writes one line per refusal to standard error, and
exits **1**:

```text
refused <file>:<line> <kind>: <reason>
```

A usage error exits **2**. Its proofs are `ci/wizroom/test_split.py`
(`python3 -I ci/wizroom/test_split.py`), on the synthetic trees in
`ci/wizroom/fixtures/`. CI runs them in the always-run set
(`.github/actions/docs-only/test.sh`).

The checker runs at three points: on OpenWiz `main` for WM1's information
report; before WM3's import, where its move set is the exact list of files
WizRoom imports and its stay set is exactly what WM2 moved to the collector
folder (so, at WM2's head, the folder holds only the move set); and before
WM9's removal, where nothing public may reach the folder.

## Caller-supplied loads

A load supplied wholly by its caller, through an argument or environment
variable with no repository default, adds no repository dependency of its own.
Only the following sites have that classification. Every unlisted dynamic
load remains subject to the refusal rule above; a repository path or default
still counts as a dependency. Placement follows the existing static in-tree
callers: the replay stays with `bench_reads.py`, and the timing harness stays
with launch-fleet's test runner and its `gh.py`. Neither harness changes its
accepted inputs. These are load-site declarations, never `--own` exemptions.

| Site | Classification |
| --- | --- |
| `skills/launch-fleet/scripts/fixtures/timing-gh.py:22` | caller-supplied |
| `tools/collector/fixtures/activity/replay.py:78` | caller-supplied |

## The public collector folder

The stay set leaves the folder for **`tools/collector/`** in OpenWiz (WM2),
moved with `git mv` so `git log --follow` keeps each file's history. Every
public consumer is repointed in the same change. The collector contract keeps
its schema id and version; only its location and links change.

## WizRoom's layout

- WizRoom's `main` keeps the war room under the **same repository-relative
  folder, `tools/war-room/`**, so every repository-relative path in the code
  keeps working with no code change for the move.
- WizRoom's `main` holds only code of public OpenWiz origin and committed
  templates. Samples live only on its `war-room` data branch; secrets live only
  in repository secrets and the machine's local settings file.
- History: WizRoom's `main` is made from OpenWiz's public history of the move
  set, filtered so each commit keeps only those files, with a source-commit map
  (`docs/import-map.tsv`: each imported commit and its OpenWiz commit). No
  private-record history is copied into `main`.

## The OpenWiz pin

One reviewed file at WizRoom's root, **`openwiz.json`**, names the OpenWiz
commit WizRoom runs against, in the same one-field form as the private
record's publisher pin today:

```json
{"code_commit": "0123456789abcdef0123456789abcdef01234567"}
```

Exactly one key, `code_commit`, a full lowercase 40-hex commit id (the example
is synthetic). **The on-`main` check**: every WizRoom workflow, before it runs
anything else, fetches OpenWiz `main` and refuses unless the pinned commit is
an ancestor of it or equal to it (`git merge-base --is-ancestor <pin>
origin/main`). A malformed pin, a fetch failure or a commit not on `main`
fails the job. Moving the pin is an ordinary WizRoom pull request.

## The pin-and-replace checkout

Every WizRoom workflow runs the war room inside OpenWiz at the pin:

1. check out WizRoom;
2. read `openwiz.json` and check out public OpenWiz at that commit, with
   WizRoom's own token and no persisted credentials;
3. run the on-`main` check;
4. delete that checkout's `tools/war-room/` and copy WizRoom's `tools/war-room/`
   in its place;
5. run every step from the OpenWiz checkout's root.

Nothing else from WizRoom enters the OpenWiz checkout, and nothing is pushed to
OpenWiz.

## The `war-room` data branch: one writer, fast-forward only

- **One writer.** At most one publisher, the private record's or WizRoom's, is
  switched on at any time.
- **Fast-forward only.** The `war-room` branch, in either repository, only ever
  moves by fast-forward: no force-push, reset, rebase or deletion. Moving
  history across (step 3b) and every way back are fast-forwards.

Together these keep both copies of the history consistent through the parallel
run, the cut-over and any way back. A publisher whose push would not be a
fast-forward publishes nothing and keeps the last good site.

## Variables and the one secret

| Name | Kind | Values | Meaning |
| --- | --- | --- | --- |
| `WAR_ROOM_PUBLISH` | WizRoom repository variable | `on`; anything else, or unset, is off | The publishing switch. Off by default. Pull requests never publish |
| `WIZROOM_RUNS_ON` | WizRoom repository variable | a runner label | Every WizRoom job's runner, `${{ vars.WIZROOM_RUNS_ON \|\| 'jog-4vcpu' }}`. Unset means `jog-4vcpu`. Hosted runners are never the default |
| `BOARD_READ_TOKEN` | WizRoom repository secret | a fine-grained token | The one cross-repository credential (scope below) |

`BOARD_READ_TOKEN`'s scope: one repository, the private record; one
permission, **Contents: read-only**; used only by the publishing workflow to
fetch the private record's `board` branch. It never writes, and no other job
reads it. Public OpenWiz is read with WizRoom's own workflow token. Nothing else
crosses repositories.

## The adapter's local settings

The serving adapter on the machine reads one local settings file,
`$XDG_CONFIG_HOME/wizroom/adapter.env` (default `~/.config/wizroom/adapter.env`).
It is **never committed**; WizRoom commits only a synthetic example. Each
setting is required, and a missing or empty one refuses the install:

| Setting | Meaning |
| --- | --- |
| `WIZROOM_ADDRESS` | The loopback address the adapter listens on |
| `WIZROOM_PORT` | The port it listens on |
| `WIZROOM_REMOTE` | The Git remote it fetches the `war-room` branch from |
| `WIZROOM_CREDENTIAL` | Where the fetch credential comes from (a credential helper or file path), never the credential itself |

**The same-port rule.** The live adapter listens on exactly `WIZROOM_PORT`,
which is the port the existing tunnel already routes to, so no tunnel, DNS,
Access or Cloudflare setting changes. Install refuses any unit that would
listen on another port. The shadow run (step 2) uses a scratch folder and a
scratch port, both given explicitly to install, and the scratch port must
differ from `WIZROOM_PORT`. Install backs up every unit it replaces, byte for
byte; restore puts the backup back.

## Cut-over steps and ways back

| Step | What happens | Read-back | Way back |
| --- | --- | --- | --- |
| 0 | OpenWiz's public layer moves to `tools/collector/` (WM2). The live publisher keeps its older pin | OpenWiz CI green. A preview at the new commit still works for the old publisher | Revert the OpenWiz pull request. Nothing live used it |
| 1 | WizRoom is imported and its CI runs on Jog (WM3) | WizRoom CI green. Its `tools/war-room/` tree equals OpenWiz's at the pin | Nothing live: close or revert |
| 2 | Shadow (WM7): the data branch is copied, WizRoom previews from real sources with publishing off, and the new adapter fetches into a scratch folder on a scratch port | Branch head and sample hashes equal. Six pages render and pass the privacy scan. Six routes answer on the scratch port | Stop and remove the scratch units and folder. The live adapter was never touched |
| 3a | The old publisher's switch goes off, after any running publication finishes | The switch reads off and no run is in progress | Turn the switch back on |
| 3b | WizRoom's `war-room` branch fast-forwards to the old branch's head | Heads equal | None needed: nothing serves WizRoom yet |
| 3c | WizRoom's publishing goes on and is dispatched once | One new publication commit on top. Six pages and privacy scan pass | WizRoom off. Fast-forward the old branch to WizRoom's head. Old switch on |
| 3d | The machine switches its units to WizRoom's adapter and remote, on the same port, with the old units backed up first | Six routes answer locally. A signed-out request from outside still gets the login, never a page | Restore the backed-up units, then step 3c's way back |
| 3e | The hourly loop dispatches WizRoom's workflow, not the old one | The next hourly publication lands on WizRoom and is fetched | Point the loop back, with 3c's way back |
| 4 | Watch window: WizRoom publishes every hour and the machine serves each publication | The watch-window gate below | Any way back above, still available |
| 5 | Only now, removal: OpenWiz drops its war-room copy and workflows and leaves a public note (WM9). The private record drops its war-room workflow, its pin and its switch, under one exception granted at that step (WM10); its `war-room` branch stays as a read-only archive | Searches clean. CI green in both. The site still updates | Revert either pull request. The old data branch is kept, so the old path can be rebuilt |

Each step's read-back is recorded privately before the next step starts. A
failed read-back stops the cut-over and takes that step's way back.

## The watch-window gate

Step 5 may start only after **24 consecutive hourly publications**: for each
of 24 consecutive hours, one new WizRoom publication commit lands on WizRoom's
`war-room` branch, and the machine fetches it and serves it on all six routes.
A missed hour, a failed publication, a failed fetch or a route that does not
serve that publication breaks the run, and the count starts again. The record of the 24 (publication commits, fetch and route answers) is
private evidence, dated before either removal merges.

## The freeze

From the merge of WM3's import until WM9's removal merges, **OpenWiz's
`tools/war-room/` takes no change**. A war-room change in that window goes to
WizRoom. Before the removal, WM9 confirms the folder is byte-identical to the
import's source commit (`git diff --quiet <source commit> HEAD --
tools/war-room/`) and that the checker reports nothing public reaching it; a
difference stops WM9 until the change is replayed into WizRoom.
