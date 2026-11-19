# Records v1 test kit

Checks a tracker against [records v1](../records.v1.md) and prints every record that breaks a rule. Python 3.11 or later, standard library only. It only reads.

```sh
python3 -I kernel/records-kit/check.py --fixture <tracker.json>   # a fixture tracker
python3 -I kernel/records-kit/check.py --repo <owner>/<name>      # a real repository, read through gh
python3 -I kernel/records-kit/test_check.py                       # the kit's own tests, on fixtures/
```

Each break is one line, `#<issue> <rule>: <what>`, for example `#2 L1: label building says what an agent is doing; read it from GitHub`. Lines come in issue order, then in the spec's rule order. Exit 0: no break. 1: breaks printed. 2: the tracker could not be read. Then it prints the reason on stderr, `check.py: <why>`, and reports nothing.

## The tracker

A fixture is one JSON object with exactly these keys. A missing, extra or repeated key, or a value of another type, makes the tracker unreadable (exit 2); nothing is guessed.

| Key | Value |
| --- | --- |
| `tracker` | `openwiz:records-kit tracker v1` |
| `repo` | `<owner>/<name>` |
| `now` | The time the tracker was read, UTC `YYYY-MM-DDTHH:MM:SSZ`; a status note is live while edited less than 30 minutes before it |
| `record_authors` | The logins whose status notes count, compared case-insensitively |
| `issues` | The open issues, each with exactly `number`, `labels` (names), `parent` (its parent issue's number, or `null`), `blocked_by`, `body` and `comments` |

Each `blocked_by` entry is a native blocker: `number`, `state` (`open` or `closed`) and `state_reason` (`null` while open; `completed`, `not_planned`, `duplicate` or `null` once closed). Each comment has `id`, `author` (a login; an App's ends `[bot]`), `updated_at` and `body`.

`--repo` builds the same tracker from GitHub: the open issues with their labels, parent, native blockers and every comment, and the record authors from the repository's `docs/agents/fleet.md` (its `Record authors` row). It needs a signed-in `gh` with read access. An answer it can't read whole refuses (exit 2).

## Which issues are what

- A **ticket** is an open issue with a parent; the parent is its spec.
- A **spec** is an open issue without a parent that carries `spec`, or that is the parent of an open issue in the tracker.
- L3 checks a ticket's spec only when that spec is open (in the tracker).

## Fixtures

`fixtures/valid.json` passes. It holds a lapsed note exactly 30 minutes old, a record author's name in another case, a v1 marker from someone who isn't a record author, a v2 note, a heading inside a code block and a project's own label. Each `fixtures/broken-<name>.json` is that tracker with one planted break; `test_check.py` names the exact lines each must print.
