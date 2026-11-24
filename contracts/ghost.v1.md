# OpenWiz ghost text contract, version 1 (`openwiz.ghost.v1`)

Ghost text in any composer from one local engine. This contract pins the words, HTTP routes, stdio JSON-lines framing, pairing and Origin rules, refusal shapes, context pack, event log line, bench report, and golden fixtures that spec #3148 (0.2.0) builds against. Its schema is [ghost.v1.schema.json](ghost.v1.schema.json); its synthetic golden fixtures are in [`contracts/fixtures/ghost/`](fixtures/ghost/).

**Contract only** (#3149, GS1). GS2 (#3150) builds the loopback HTTP and stdio engine with recall, pairing and Origin checks; GS3 (#3151) adds the small local model tier and blending; GS4 (#3152) adds `openwiz ghost bench`, the CI gate and the opt-in local log; GS5 (#3153) adds precomputed harness drafts; GS6 (#3155) adds the `ghost` skill and learn pass; GS7 (#3154) and BB1 (`WizPlugins#251`) add T3 Code and BB composers; WS1–WS3 (`WizSite#239`–`#241`) add the OpenWiz app composer. Fixtures prove shapes and expected answers, never live behaviour.

Authority: spec #3148, its confirmed ghost-text grill of 2026-11-24 (private record), and the lead ruling on #3149 (2026-11-24).

## Words

| Word | Meaning here |
| --- | --- |
| **Ghost** | The gray suffix shown after the caret (`suggestion.text`). `full_text` is `prefix + text`. |
| **Recall tier** | Under-5 ms n-gram and entity trie over the context pack. Exists in both the engine and the browser module, bound by the same golden fixtures. |
| **Small model tier** | Local model server (llama-server or Ollama, raw completion, no chat template) blended with recall, p90 <= 150 ms keystroke to ghost. |
| **Draft tier** | Whole-reply draft from the user's own signed-in harness CLI, precomputed when an agent turn asks the user something. Never auto-sent. |
| **Context pack** | Precomputed snapshot of the user's skill file, glossary, open work and last three conversation turns, in stable-to-volatile order. Never rebuilt per keystroke. |
| **Surface** | The composer calling the engine: `openwiz-app`, `t3-code`, `bb-plugin`, `cli`, or `other`. |
| **Pairing token** | Opaque bearer secret minted once by exchanging the one-time code from `openwiz ghost pair` on `POST /ghost/v1/pair`. |

## Transport, Host, Origin and pairing rules

### HTTP (`openwiz ghost serve`)

- **Bind address:** `127.0.0.1` only (default port `17417`, configurable). Never binds `0.0.0.0` or any non-loopback address.
- **Routes:** every route is `POST /ghost/v1/<route>` with `Content-Type: application/json` and a UTF-8 JSON body (at most 1 MiB).
  Routes: `pair`, `health`, `context`, `turns`, `complete`, `draft`, `feedback`, `bench`.
- **CORS preflight:** `OPTIONS /ghost/v1/<route>` runs the `Host` check then the `Origin` check. When `Origin` is present and on the allowlist, respond `204 No Content` with `Access-Control-Allow-Origin: <exact Origin>`, `Access-Control-Allow-Methods: POST, OPTIONS`, `Access-Control-Allow-Headers: Authorization, Content-Type`, `Access-Control-Allow-Private-Network: true`, and `Vary: Origin`. When `Origin` is absent or not allowed, refuse with `403`.
- **Check order on every HTTP request (stop at first failure):**
  1. **Host:** `Host` header must be `127.0.0.1`, `127.0.0.1:<port>`, `localhost`, or `localhost:<port>`. Otherwise `403` `host_not_allowed`.
  2. **Origin:** if an `Origin` header is present, it must match the allowlist exactly:
     - `https://openwiz.dev`
     - `https://<label>.wizsite.pages.dev` (`<label>` is one lowercase ASCII DNS label, `[a-z0-9]` with interior `-`, 1–63 chars, no dots)
     - `http://localhost` or `http://localhost:<port>`
     - `http://127.0.0.1` or `http://127.0.0.1:<port>`
     Otherwise `403` `origin_not_allowed`.
     A request with **no `Origin` header** is allowed with a valid pairing token (or valid one-time code on `pair`), so non-browser local clients (sidecars, plugin hosts) work without spoofing `Origin`, while browsers always send `Origin` on cross-origin fetches and cannot drop it.
     Responses to allowed-`Origin` requests echo `Access-Control-Allow-Origin: <exact Origin>` and `Vary: Origin`.
  3. **Pairing token:** required on every HTTP route except `POST /ghost/v1/pair`, as `Authorization: Bearer <token>` compared in constant time. Missing or non-Bearer header -> `401` `missing_token`; unknown or revoked token -> `401` `invalid_token`. On `POST /ghost/v1/pair`, an invalid, expired or already-used one-time code -> `401` `invalid_pairing_code`.
  4. **Method, route and body:** non-`POST` (other than `OPTIONS`) -> `405` `method_not_allowed`; unknown route -> `404` `unknown_route`; body over 1 MiB -> `413` `payload_too_large`; invalid JSON or schema mismatch -> `400` `invalid_request`.

### Refusals

Every HTTP error response (and every stdio error response body) is a `#/$defs/refusal` JSON object:

```json
{"refusal":{"code":"origin_not_allowed","message":"Origin is not on the ghost.v1 allowlist."}}
```

| HTTP status | Code | Meaning |
| --- | --- | --- |
| 400 | `invalid_request` | Malformed JSON or body fails schema validation |
| 401 | `missing_token` | Missing or non-Bearer `Authorization` header on HTTP |
| 401 | `invalid_token` | Unknown or revoked pairing token |
| 401 | `invalid_pairing_code` | Unknown, expired or already-used one-time pairing code |
| 403 | `host_not_allowed` | `Host` header is not loopback |
| 403 | `origin_not_allowed` | `Origin` header is present and not on the allowlist (or missing on `OPTIONS`) |
| 404 | `unknown_route` | Route name is not one of the eight `ghost.v1` routes |
| 405 | `method_not_allowed` | HTTP method is not `POST` (or `OPTIONS` for preflight) |
| 413 | `payload_too_large` | Request body exceeds 1 MiB |
| 501 | `not_implemented` | Route or subcommand is stubbed and not built yet |
| 503 | `unavailable` | Local dependency (e.g. configured draft harness) is unavailable |

### Stdio (`openwiz ghost --stdio`)

One UTF-8 JSON object per line (`\n`-delimited) on stdin; one compact JSON object per line on stdout. **Stdio needs no pairing token** (and runs no `Host` or `Origin` check): only the process that spawned the engine can write to its stdin.

- **Request (`#/$defs/stdio_request`):** `{"id":"req-1","route":"complete","body":{...}}`
- **Response (`#/$defs/stdio_response`):** `{"id":"req-1","status":200,"body":{...}}`
  On error, `status` is the HTTP status code from the refusal table above and `body` is a `#/$defs/refusal`. If an input line cannot be parsed as a JSON object with a string `id`, `id` is `null` and `status` is `400`.

## Routes

Every route schema pair is defined in `ghost.v1.schema.json` as `<route>_request` and `<route>_response`.

| Route | Request | Response |
| --- | --- | --- |
| `POST /ghost/v1/pair` | `{code, surface}` | `{schema, token, surface}` |
| `POST /ghost/v1/health` | `{}` | `{schema, status, version, tiers:{recall,small_model,draft}, logging_enabled, context_revision}` |
| `POST /ghost/v1/context` | `{if_revision?}` | `{schema, revision, unchanged, pack}` (`pack` is `#/$defs/context_pack`, or `null` when `unchanged` is `true`) |
| `POST /ghost/v1/turns` | `{session_id, agent, turns}` (0–3 turns, oldest first) | `{schema, revision, draft_queued}` (starts precomputed draft when last turn has `asks_user: true`) |
| `POST /ghost/v1/complete` | `{session_id, surface, prefix, seq}` | `{schema, seq, suggestion}` (`suggestion` is `{id, text, full_text, tier, confidence, latency_ms}` or `null`) |
| `POST /ghost/v1/draft` | `{session_id, surface}` | `{schema, draft}` (`draft` is `{id, text, precomputed, latency_ms}` or `null`; never sent) |
| `POST /ghost/v1/feedback` | `#/$defs/event` | `{schema, recorded, logged}` (`logged` is `false` unless opt-in local log is on) |
| `POST /ghost/v1/bench` | `{source, surface, replay_path?}` | `#/$defs/bench_report` |

`complete` rules:
- `seq` is a monotonic nonnegative integer per `session_id`; a newer `seq` supersedes any in-flight request, and a stale reply is dropped.
- `suggestion.text` is the suffix after the caret (1–8 words, ending at a word or sentence boundary); `suggestion.full_text` equals `prefix + suggestion.text`.
- When confidence is below the tuned threshold (start: `0.30`) or nothing matches, `suggestion` is `null`.
- Typed-through characters and word accepts consume the cached suggestion client-side with zero requests.

## Context pack (`#/$defs/context_pack`)

Rebuilt on record changes, sent/received messages or learn-pass completion; never per keystroke. Sections are ordered **stable to volatile** so the local model server's prefix cache survives across keystrokes:

1. **`skill`** (most stable): `{phrases, tone, never_suggest}` — user's personal skill file and lexicon.
2. **`glossary`**: `[{term, meaning}]` — settled project terms.
3. **`open_work`**: `{specs:[{number, title}], tickets:[{number, title, action}], grills:[{code, question, recommended}]}` — open specs, tickets and decisions waiting on the user with recommended answers.
4. **`conversation`** (most volatile): `{session_id, agent, turns:[{role, text, asks_user}]}` — current agent and at most the last three turns.

## Event log line (`#/$defs/event`)

Opt-in local JSONL log (off by default, stored only on the user's machine, deleted by `openwiz ghost forget`). Also the request body of `POST /ghost/v1/feedback`:

```text
event { schema: "openwiz.ghost.v1", kind: "event", at, suggestion_id, session_id,
        surface, outcome, tier, confidence, latency_ms, chars_accepted }
```

- `outcome`: `shown` | `accepted_all` | `accepted_word` | `typed_through` | `dismissed` | `typed_over`
- `tier`: `recall` | `small_model` | `draft`
- `confidence`: number in `[0, 1]`
- `latency_ms`: number >= `0`
- `chars_accepted`: nonnegative integer (`0` for `shown`, `dismissed`, `typed_over`)

## Bench report (`#/$defs/bench_report`)

Printed by `openwiz ghost bench` and returned by `POST /ghost/v1/bench`:

```text
bench_report { schema: "openwiz.ghost.v1", kind: "bench_report", source, messages,
               overall, per_tier: [{tier, metrics}], per_surface: [{surface, metrics}] }
bench_metrics { shown, accepted, acceptance_rate, chars_saved_per_message,
                suggestions_per_message, p50_latency_ms, p90_latency_ms }
```

- `acceptance_rate`: `accepted / shown` in `[0, 1]` (`0.0` when `shown` is `0`).
- `chars_saved_per_message`: accepted characters still present in the sent message, averaged per message.
- `per_tier` and `per_surface` are arrays (not maps) so the dependency-free schema validator checks every entry strictly.

## CLI subcommands (`openwiz ghost`)

| Command | Purpose | GS1 stub behaviour |
| --- | --- | --- |
| `openwiz ghost serve` | Run the loopback HTTP engine on `127.0.0.1` | Exits `5`: `ghost serve is not built yet` |
| `openwiz ghost --stdio` | Run the JSON-lines stdio engine (no pairing token) | Exits `5`: `ghost --stdio is not built yet` |
| `openwiz ghost pair` | Print a one-time pairing code for `POST /ghost/v1/pair` | Exits `5`: `ghost pair is not built yet` |
| `openwiz ghost bench` | Replay messages and print `#/$defs/bench_report` | Exits `5`: `ghost bench is not built yet` |
| `openwiz ghost forget` | Delete the opt-in local ghost event log | Exits `5`: `ghost forget is not built yet` |
| `openwiz ghost --help` | Print `ghost` usage | Exits `0` |

Unknown or missing subcommands exit `2` (usage).

## Golden fixtures (`contracts/fixtures/ghost/`)

All synthetic, built on the app demo's fictional records:

| File | Schema `$def` | Contents |
| --- | --- | --- |
| `context-pack.json` | `context_pack` | Synthetic skill phrases, glossary, open work (grill `J1`, ticket `#42`, spec `#12`), and conversation turns |
| `recall-cases.json` | `recall_fixture_set` | Step sequences (`type`, `accept_word`, `accept_all`, `dismiss`) covering all six spec recall table rows plus typed-through, word-accept and Esc cases |
| `replay-set.json` | `replay_fixture_set` | Small synthetic message replay set for `openwiz ghost bench` |
| `messages.json` | each route / record `$def` | Valid synthetic sample for every request, response, refusal, stdio envelope, event and bench report |

`crates/cli/tests/ghost_contract.rs` lints the schema, validates every fixture and sample, verifies every spec recall row and interaction case is present, tests negative schema rejections, and runs the `openwiz ghost` stub commands.
