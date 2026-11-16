# OpenWiz engine retirement map, version 1 (`openwiz.engine-retirement.v1`)

This map says what the web view, the kept CLI and the kept loop features need, and
what each removal ticket of spec #786 (0.0.17) may delete. ER2 (#796), ER3 (#797),
ER4 (#798) and ER6 (#800) delete only what their section below lists. ER5 (#799)
and Infra MT9 (#828) stop calling only what their sections list.

**Contract only** (ER1, #795). It changes no code. Its build check (the last section)
was run on a scratch copy with each removal's files left out, and nothing from it was
committed. Fixture builds and fixture tests prove only that the kept code compiles and
its tests pass without the deleted files. They prove nothing about live behaviour.

Base: `main` at `192f6e4`; ER3's section was re-checked at `3228599`. A removal that starts from a later `main` re-checks
its section against that `main` first. A file listed here that has changed since
is read again before it is deleted.

## Words

| Word | Meaning here |
| --- | --- |
| **Kept** | Stays, with its behaviour unchanged: the web view and its local server, the CLI (`fleet due` and every read), the existing loop features, and the GitHub and Cloudroom adapters' reads (spec #786, "Kept"). |
| **Delete** | The whole file or folder goes, with its `mod`, `[[test]]` or import line. |
| **Edit** | Only the named part of a file goes; the rest stays as it is. |
| **Path gap** | A file the removal must edit that is not in its ticket's owned paths. Granted narrowly, same intent, by D4 below: the removal may make exactly the edit listed here and lists it in its pull request. Anything beyond it is asked on its ticket, as build-ticket says. |
| **Left for later** | Needed by nothing kept and not named for retirement. It stays, listed in "Left for later", for a later decision (spec #786, "Out of Scope"). |
| **Keeper** | A kept test that still catches what a deleted test caught. |

## 1. What the web view needs

Every page goes through `crates/server` (`openwiz-server`, or embedded by
`openwiz-service` through `crates/service/src/web_api.rs` `start`). The server's
shared parts serve every route: `lib.rs` (routing, `Shared`, start
variants), `api.rs` (route table, core runs), `http.rs` and `web.rs` (static export).

| Page (`apps/web`) | Routes | Server modules | Core, store and adapter modules |
| --- | --- | --- | --- |
| Sessions, session detail (`Inventory.tsx`, `Detail.tsx`, `viewer.ts`) | `GET /api/v1/inventory`, `GET /api/v1/sessions/{id}` | `api.rs` | core `ops`, `source`, `envelope`, `model`, `limits`; cloudroom `source.rs`, `locate.rs`, `process.rs`, `allowlist.rs` |
| Send (`Composer.tsx`, `composer.ts`, `messaging.ts`) | `GET …/{id}/preview`, `POST …/{id}/messages`, `GET …/{id}/messages/{op_id}` | `send.rs` | core `messaging/*`, `prompt`, `attachment`; store `lib.rs` (`FileStore`); cloudroom `messaging.rs` |
| New thread (`Launcher.tsx`, `launcher.ts`, `newthread.ts`) | `GET /api/v1/cloud-options`, `POST /api/v1/projects/{id}/threads/preview`, `POST /api/v1/projects/{id}/threads`, `GET /api/v1/new-threads/{op_id}` | `new_thread.rs`, `send.rs` (slots) | core `new_thread/*`, `prompt`; store `new_thread.rs`; cloudroom `new_thread.rs` |
| Attachments (`AttachmentTray.tsx`, `attachments.ts`) | `GET`/`POST /api/v1/attachments`, `DELETE /api/v1/attachments/{id}` | `attachments.rs` | core `attachment`; store `attachments.rs` |
| Connection state (every page) | `GET /api/v1/health` | `api.rs` | none (server metadata; no `room-cli` read) |
| Cockpit (`Cockpit.tsx`, `cockpit.ts`), with its ready stock (`ReadyStock.tsx`, `readyStock.ts`) | `GET /api/v1/cockpit` | `cockpit.rs`, `ready_stock.rs`, `fleets.rs` | core `fleet/{agents,fleets,model,tickets}`, **core `notifications/{model,stock}`**; github `fleets.rs`, `tickets.rs`; cloudroom `fleet.rs` |
| Home, Fleets, fleet detail (`HomeLive.tsx`, `Fleets.tsx`, `FleetDetail.tsx`, `FleetProgress.tsx`) | `GET /api/v1/fleets`, `GET /api/v1/fleets/{spec}` | `fleets.rs` | core `fleet/*`; github `fleets.rs`, `tickets.rs`; cloudroom `fleet.rs` |
| Plan (`PlanGraph.tsx`, `plan.ts`) | `GET /api/v1/plan` | `plan.rs` | github `plan.rs`, `plan_reads.rs` |
| Decisions (`Decisions.tsx`, `decisions.ts`) | `GET /api/v1/decisions` | `decisions.rs` | github `decisions.rs`, `decisions_json.rs`; **core `notifications/model`** (`DecisionRef`, `TargetState`); **core `health/model`** (`Repository::parse`) |
| Loops (`Loops.tsx`, `loops.ts`) | `GET /api/v1/loops`, `POST /api/v1/loops/{name}/on`, `POST /api/v1/loops/{name}/off` | `loops.rs` | store `loops/*`; core `fleet/starts` |
| Setup (`pages/setup.tsx`, `Setup.tsx`, `CloudRoomSetup.tsx`, `setup.ts`) and First hour (`FirstHour.tsx`) | `GET /api/v1/setup` | `setup.rs` | store `setup.rs`; cloudroom `source.rs` |
| Installable app shell (`public/sw.js`, `pwa.test.ts` P1 to P8) | static export only | `web.rs` | none |

The bold rows are why ER3 and ER4 cannot delete all of `crates/core/src/health/` and
`crates/core/src/notifications/` (sections 4 and 5).

**Not a page:** push notifications are a panel under the Cockpit
(`ConnectedNotifications`) and the `#notification=<token>` landing
(`NotificationTarget`). Neither has a navigation button, so ER4 changes no
navigation entry (see ER4, "Web").

## 2. What the kept CLI needs

| Command | Modules |
| --- | --- |
| `ls`, `show`, `help`, `help --agent` | cli `lib.rs`, `agent_help.rs`, `agent-catalogue.json`, `response.rs`; core `ops`, `source`, `envelope`; cloudroom `source.rs`, `locate.rs` |
| `send` | cli `send.rs`, `attach.rs`; core `messaging/*`; store `FileStore`; cloudroom `messaging.rs` |
| `new`, `new --status`, `models` | cli `new_thread.rs`; core `new_thread/*`; store `new_thread.rs`; cloudroom `new_thread.rs` |
| `attachment add`, `ls`, `rm` | cli `attachment.rs`; core `attachment`; store `attachments.rs` |
| `fleets`, `fleet <spec>` | cli `fleets.rs`, `fleet.rs`; core `fleet/*`; github `fleets.rs`, `tickets.rs`; cloudroom `fleet.rs` |
| `fleet due --github-only` | cli `fleet_tick.rs` (its `due` path), **`fleet_tick_graph.rs`**, **`fleet_tick_records.rs`**; core `fleet/tick/*` (the planner); github `tick.rs` (`TickReads` and every read on it), `fleets.rs`, `process.rs` |
| `fleet tick --dry-run` (a kept read; D1) | the same as `fleet due`, plus cloudroom `source.rs` for the CloudRoom facts |
| `loop` | cli `loops.rs`; core `loops/*`; store `loops/*` |
| `github token` | cli `github_token.rs` |
| `ui` | cli `ui.rs` (and `crates/terminal`, whose removal is #776's) |

`fleet_tick_records.rs` is listed in ER6's owned paths as a whole file, but the
kept `fleet_tick_graph.rs` calls 19 of its functions. ER6 edits it (section 7); it
must not delete it.

## 3. What the kept loop features need

| Feature | Modules and tests |
| --- | --- |
| Loop definitions, switches, storage | store `loops/{config,document,paths,repository,storage}.rs`; server `loops.rs`; cli `loops.rs`; core `loops/*` |
| Loops page | `apps/web/src/components/Loops.tsx`, `src/loops.ts` |
| The scheduler code and loop runner | service `loops/{approval,check,limits,production,mod}.rs`, `scheduler.rs`, `runtime.rs` (the loop registration line) |
| Loop health (kept by ER3) | the registered `health` job, reduced to the LP4 watchdog: service `health/mod.rs` (watchdog pass and record delivery), `watchdog.rs`, `records.rs`, `loops.rs` (LP4's planner), `loops::observe`; its state in `document.rs` and `state.rs` |
| Tests | `tests/loops/*`; `tests/service/l3_*`, `l10_approval.rs`, `l11_limits*`, `l12_registration.rs`, `l5_watchdog.rs`, `l5b_watchdog.rs`, `l5b_observation.rs`, `install_engine_loops.rs` |

`tests/loops/l6_api.rs` and `tests/service/l12_registration.rs` are kept loop tests
that ER4 and ER3 must edit, and say so in their pull requests (sections 4 and 5).

## 4. ER3 (#797): retire health and takeover

**Loop health stays as a report-only job** (#797: "Loop health stays"). Today LP4's
watchdog runs inside the health pass. It shares that pass's `incidents`,
`next_incident` and `last_pass`, and it reports through the health records (a
record comment on the service issue) and the Needs-you send to the orchestrator.
ER3 keeps that path, the registered `health` job, with the watchdog as its only
check. It deletes the other checks (`cloudroom`, `loop`, `tick`, `fleet_thread`,
`server`), every repair fix (resume loop, restart tick, restart server), takeover and
the runtime restart channel.

**Delete**

- `crates/service/src/health/`: `model.rs`, `observe.rs` (move its `authored` into `records.rs`; the #770 delivery read-back uses it), `runtime.rs`, `takeover.rs`
- `tests/service/`: `t3_planner.rs`, `t3_checks.rs`, `t3_contract.rs`, `t3_owned.rs` (and `mod t3_planner;` in `main.rs`); the whole `t5-health` target: `t5_health.rs`, `t5_server.rs`, `t5_restart.rs`, `t5_execution.rs` (after moving the delivery tests below), `t5_runtime.rs`, `t5_takeover.rs`, `t5_takeover_execution.rs`, and `t5_tick.rs` if ER2 has not already deleted it (it hangs off `t5_health.rs`)

**Keep**

- `crates/service/src/health/loops.rs` (LP4's planner), `watchdog.rs` (the production observation and `apply`), `records.rs` (record render, freeze, post, reconcile and the record-author read-back).
- In `crates/service/src/health/mod.rs`: `WatchdogRead`, `Sources`, `Health` (without `runtime` and `pending`), `with_watchdog_source`, `register` (it no longer takes the server port), `snapshot`, `change`, `repository`, `patch` and `flush_records`. `pass(now)` becomes the watchdog pass: take the pass lock, check the repository, flush and reconcile pending records, run `watchdog::apply` into `incidents`, `next_incident` and `last_pass`, then flush again. Delete `RuntimeFixes`, `Pending`, `observe`, `recover`, `save_outcome`, and the planner, takeover and fix parts of `pass`.
- `crates/service/src/loops/mod.rs`'s `observe`, and `tests/service/l5_watchdog.rs`, `l5b_watchdog.rs`, `l5b_observation.rs`.

**Edit**

- `crates/core/src/health/mod.rs` and `model.rs`: keep only `model::{Id, Number, Repository, SeenLoop}`, `is_openwiz_loop` and `HEALTHY_FOR_MS`. `crates/adapters/cloudroom/src/loops.rs` uses `Id`, `Repository`, `SeenLoop` and `is_openwiz_loop`. `crates/adapters/github/src/decisions.rs` (the Decisions page) uses `Repository::parse`, and the kept `records.rs` uses `Number`. `HEALTHY_FOR_MS` stays only while ER4 has not merged (`crates/service/src/notifications/sources.rs` reads it).
- `crates/core/src/lib.rs` and `crates/service/src/lib.rs`: nothing; both `health` lines stay.
- `tests/service/l5b_watchdog.rs` (shared: its harness only): drop `RuntimeFixes` and `seen()`, call `Health::new` without a runtime, `pass(now)` and `register(&mut scheduler, now)`. Every assertion stays (checked: 12/12 pass).
- `contracts/service.v1.md`: "The checks" and "A result" keep only the `watchdog` result. "Incidents and the two-tries rule" keeps watchdog incidents and their Needs you (watchdog incidents have no tries). "Records" keeps the watchdog's record line. Delete "TK1: takeover by the service tick" and "Public fleet ownership discovery". "LP4: the independent loops watchdog", the `health` row of "The config", and the `incidents`, `watchdog_deliveries` and `last_pass` parts of "The status report" and "The state" stay.

**Path gaps** (outside ER3's owned paths; granted by D4)

- `crates/service/src/runtime.rs` (shared: the health wiring): drop `channel_with_monitor` and the `health_requests` loop, and call `Health::new` without a runtime and `register` without the port. `run_with_health_sources` and its `sources` parameter stay, because `health::Sources` stays.
- `crates/service/src/document.rs` (shared: S1): drop "cloudroom first" and the required `cloudroom`, `tick` and `server` results. A pass with only the watchdog result is then valid. S7's fix checks see no fixes. Old state files with the retired results still read.
- `crates/service/Cargo.toml` (shared: the `t5-health` `[[test]]` entry).
- `tests/service/l12_registration.rs`, `notifications_engine.rs` and `notifications_delivery.rs`: no change. The health job still runs and writes `last_pass` (checked: 17/17, 33/33 and 5/5).

**Move, never delete:** the delivery tests in `t5_execution.rs` protect `records.rs`, which stays. ER3 moves each onto watchdog incidents in `l5b_watchdog.rs`, or names the `l5b` test that already catches its bug:
- `only_the_factory_s_comments_confirm_a_health_delivery` (#770)
- `lost_record_reply_is_reconciled_without_another_post_or_resume`
- `uncertain_absent_record_never_gets_a_second_post`
- `legacy_claim_after_healing_gets_its_original_receipt_only_by_unique_readback`
- `quarantined_frozen_delivery_keeps_other_repairs_and_healing_progressing`
- `foreign_project_notification_target_is_never_sent_a_message`

The rest of `t5_execution.rs` tests repair fixes, which are gone.

**Left for later after ER3:** `crates/adapters/cloudroom/src/loops.rs` (health loop inventory, pause and resume; only the retired checks used it), `crates/service/src/scheduler.rs`'s tick monitor and restart helpers, and `document.rs`'s validation of the retired incident kinds and fixes.

**Keepers:** `l5_watchdog.rs`, `l5b_watchdog.rs` and `l5b_observation.rs` keep loop health. The moved delivery tests keep the records. Health's other checks, repairs and takeover, and its restart of the HTTP server and the tick, are gone. For `t5_server.rs`'s two server-lifecycle tests, ER3 names a keeper in `tests/web-api/` or says the behaviour (health's server restart) is gone; this map did not verify one.

**Closes as not needed:** #202 (`health::Fault::refresh`). #770 has merged and is closed.
**Stays open:** #848 (its test moves with the kept records) and #203 (`health::model::Id::as_str`, because `Id` is kept).

## 5. ER4 (#798): retire push notifications

**Delete**

- `crates/service/src/notifications/` (all)
- `crates/store/src/notifications/` (all), and `pub mod notifications;` in `crates/store/src/lib.rs`
- `crates/core/src/notifications/boundary.rs`, `grouping.rs`, `policy.rs`
- `crates/server/src/notifications.rs`, `crates/server/src/notification_target.rs`
- `contracts/notifications.v1.md`, `contracts/notifications.v1.schema.json`, `contracts/notification-delivery.v1.md`
- `tests/notifications/contract.rs`, `durable.rs`, `held_store.rs`, `journey.rs`, `policy.rs`
- `tests/service/notifications_engine.rs`, `notifications_delivery.rs`; `tests/web-api/notification_target.rs`; `tests/fixtures/notifications/`; `tools/notifications/`
- `apps/web/src/notifications.ts`, `apps/web/src/components/Notifications.tsx`, `apps/web/src/components/NotificationTarget.tsx`, `apps/web/styles/notifications.css`
- `apps/web/test/unit/notifications.test.ts`, `notificationTarget.test.ts`; `apps/web/test/browser/notification-target.test.mjs`, `notifications-delivery.test.mjs`, `notifications-journey.test.mjs`; `apps/web/test/fixtures/notification-target/`, `notifications-delivery/`, `notifications-journey/`

**Keep**

- `crates/core/src/notifications/model.rs` and `stock.rs`, and `mod.rs` naming only those two. The ready stock (`crates/server/src/ready_stock.rs`) and Decisions (`crates/server/src/decisions.rs`) use them. ER4 may trim `model.rs` to the types those two still use.
- The `notifications` test target in `tests/Cargo.toml`, with `tests/notifications/main.rs` naming only `mod stock;`. `stock.rs` tests the kept core `stock` module (7 tests; they pass with everything else deleted).
- `apps/web/src/notificationTarget.ts`: the Decisions page imports `selectBoundDecision`, `BoundDecision` and `DecisionReference` from it. Either keep only those (and drop `targetReader` and its `api.ts` imports), or remove the Decisions page's bound mode (`boundReference` and its props: only the landing uses it) and delete the file. The second needs the path gap below.

**Edit (owned)**

- `crates/server/src/lib.rs`: the two `mod` lines and the `pub use` of `notification_target`; the 7 notification `ROUTES` entries; `Shared`'s `notifications` and `notification_targets`; `start_configured`'s two parameters; `start_with_notifications`, `start_with_notifications_and_targets`, `NotificationReadSources`, `start_with_notification_targets`; the `Notification` and `NotificationTarget` arms of the request handler; `core()`'s `notifications`.
- `crates/service/src/web_api.rs`: keep `start` and `configured_target`; the embedded server starts through `openwiz_server::start_with_loop_switches` with the same `ReadSources` and loop switches. Delete the target mapping, the notification `Context` and `start_notification_api`.
- `crates/service/src/lib.rs` (shared): `pub mod notifications;`, `pub use web_api::start_notification_api;`, `NOTIFICATION_JOB`, `notification_job`, `DeliveryFactory`, `DELIVERY`, `delivery()`, `dispatch_with_delivery`.
- `apps/web/src/components/App.tsx` (shared): the notification imports, `notification` state, the `#notification` landing in the `hashchange` handler, `clearNotification` and `dismissNotification`, every `notification.kind === 'none'` guard, and `<ConnectedNotifications />` under the Cockpit. The navigation buttons do not change.

**Path gaps** (outside ER4's owned paths)

- `crates/server/src/api.rs`: the `Notification` and `NotificationTarget` routes and calls, and `Core::notifications`.
- `crates/service/src/runtime.rs` (shared: the notification job registration block).
- `crates/service/Cargo.toml` (shared: the `notifications-engine` and `notifications-delivery` `[[test]]` entries).
- `crates/service/examples/fixture.rs`: the `OPENWIZ_FIXTURE_NOTIFICATION_JOURNEY` branch and its `journey` module.
- `crates/store/src/loops/mod.rs` and `paths.rs`: only the notification store used `inspect_settled` and `Failure`. Without it, clippy's `-D warnings` fails on dead code. #818 may want them back (spec #786's note on #753's busy pattern).
- `tests/web-api/main.rs` (`mod notification_target;`) and `tests/web-api/e11_decisions_support.rs` (`serve_targets`, `serve_targets_with_clock`).
- **The web view's route tests change.** `tests/web-api/a4_no_mutation.rs` (`legacy_routes` and its catalogue mutation loop) and `tests/web-api/contract.rs` (`the_contract_documents_what_the_tests_check`) pin the notification routes, so 7 of 354 web-API tests fail until they are edited (checked). Also `tests/loops/l6_api.rs` (`route_inventory_appends_exactly_the_two_local_switch_writes`) and `contracts/web-api.v1.md` ("Notifications (0.0.15 T1, contract only)"). ER4's acceptance criterion "the web view's kept route tests pass unchanged" cannot hold for these three tests. D3 grants exactly these edits, only to remove the notification routes.
- `apps/web/src/api.ts`: the four notification imports and `readNotificationTarget`, `readNotificationStatus`, `readNotificationPreferences`, `writeNotificationPreferences`.
- `apps/web/pages/_app.tsx`: the `notifications.css` import.
- `apps/web/public/sw.js` (its `push` and `notificationclick` handlers) and `apps/web/test/unit/pwa.test.ts` (P6's event list, P9, P10). The app shell itself stays.
- `apps/web/src/components/Decisions.tsx`: only if its bound mode goes (see "Keep").

**Left for later after ER4:** `contracts/cockpit.v1.md` and `contracts/service.v1.md` mentions of notifications ("Notification job and protected state"; ER4 owns neither file, so that section goes only with a path widening); `docs/spikes/0.0.15-notifications.md`; `tools/open-import/paths.json`'s rows; `ci/select/map.json`'s rows, which the nightly run re-measures.

**Keepers:** `tests/web-api/ready_stock.rs`, `tests/notifications/stock.rs` and `apps/web/test/browser/ready-stock.test.mjs` keep the ready stock. `tests/web-api/e11_decisions_*.rs` keep Decisions. Everything else deleted is notification behaviour that is gone.

**Closes as not needed:** #536, #560, #498, #497, #534. #753 is already closed.
**Stays open:** #190 (`tools/review-relay`, which is not push notifications).

## 6. ER2 (#796): retire the service's scheduled fleet tick

**Delete**

- In `crates/service/src/tick.rs`: `register` and `register_with_sources` (the CLI-executor composition) and their imports. **Keep** `JOB` and `Sources` (the kept `crates/service/src/scheduler.rs` and `events/intake.rs` use them), and `register_with` and `register_with_control` (the scheduler and state seam that ER3's `t5-health` tests still use until ER3 merges).
- `tests/service/t4b_tick.rs`, `t4b_executor.rs`, `t4b_fake.rs`, `t4b_fleet.rs`, `t4b_schedule.rs` (the whole `t4b-tick` target)
- `tests/service/t5_tick.rs`, and its two `mod` lines in `t5_health.rs` (unless ER3 has merged)

**Edit**

- `crates/service/src/runtime.rs` (shared: the tick wiring): the `crate::tick::register(…)` line.
- `crates/service/src/lib.rs`: nothing; `pub mod tick;` stays for what remains.
- `contracts/service.v1.md` (shared: the tick section): the `tick` row of "The config" and the tick's runs in "The status report" and "The state". The `tick` check and TK1 are ER3's.

**Path gap:** `crates/service/Cargo.toml` (shared: the `t4b-tick` `[[test]]` entry).

**Left for later after ER2:** `crates/service/src/document.rs` and `state.rs`, which still read and validate `tick` config and state. After ER3, also `register_with`, `register_with_control` and the scheduler's tick helpers.

**Keepers:** `tests/fleet/b5_*` (the CLI executor, until ER6), `tests/service/t4_scheduler.rs` (the scheduler).

**Closes as not needed:** none found for ER2 alone. The tick-contract follow-ups go with ER6.

## 7. ER6 (#800): retire the start-up switch and the CLI tick

**Order:** ER6 must merge after ER2. On `main` without ER2, deleting the executor breaks `crates/service/src/tick.rs` (checked). ER6 is blocked by #795, #799 and #828 only, so this is open plan change P1.

**Delete**

- `crates/cli/src/engine.rs` (and `pub mod engine;` in `crates/cli/src/lib.rs`), `crates/cli/src/fleet_tick_execute.rs`
- `tests/service/t12_handover.rs` (and `mod t12_handover;` in `main.rs`), `tests/service/install_engine_commands.rs` (and its two lines in `t4_service.rs`)
- `tests/fleet/pre_effect.rs`, `pre_effect_input.rs` (`--expect-plan`), and their two lines in `b5_tick.rs`
- In `tests/fleet/`: the 71 executing-tick tests listed in "ER6's failing tests" below, except the two `fleet due` tests, which ER6 re-seeds

**Edit (owned)**

- `crates/cli/src/fleet_tick.rs`: delete the `execute` module line, `--expect-plan`, `read_expected`, `Control`, `run_with_control`, `run_with`, `run_selected`, recovery and `perform` in `run_observed`, and `write_diagnostic`; `fleet tick` without `--dry-run` refuses as usage. Keep `parse`, `run`, `run_observed`'s plan, `print_candidates`, `Inventory` and `World`, and `USAGE`/`HELP` for `fleet tick --dry-run` and `fleet due` (D1).
- `crates/cli/src/fleet_tick_records.rs`: delete only `fallback_record` (the executor was its one caller). The rest serves `fleet_tick_graph.rs`. Do not delete the file.
- `crates/cli/src/main.rs`: the `engine` dispatch block.
- `crates/cli/src/agent-catalogue.json`: `engine.preview`, `engine.activate`, `engine.status`, `fleet.tick` (the executing form), the `--expect-plan`, `--operation`, `--root` and `--location` flags, the `engine` help aliases, and the notes' "fleet tick" wording. `fleet.tick.preview` and `fleet.due` stay (D1).
- `contracts/cli.v1.md` ("Installed engine preparation (#1106)", and the `fleet tick` and `engine` rows), `contracts/service.v1.md` (the packaged-start parts of "Packaged update channel"), `contracts/fleet-tick.v1.md` ("Reviewed-plan execution (revision #1892)", "What each action writes", "Outcomes" and the run-mode envelope). "launch-fleet's lines", "Actions", "Facts", "Merge", "Order" and "Where each fact comes from" stay: they describe the plan `fleet due` and `--dry-run` read.
- `crates/adapters/github/src/tick.rs`: nothing. Every read on `TickReads` is still used by `fleet_tick_graph.rs`.

**Path gaps**

- `crates/cli/src/lib.rs`: `pub mod engine;` and `engine_usage` in the help text.
- `tests/proof/p08a_allowlist_static.rs`: the `ENGINE_LAUNCHER` exception, `engine_launcher_problems`, `engine_interpreter_exception_rejects_planted_widening` and its case row (it `include_str!`s `engine.rs`).
- `tests/cli-agent/main.rs` and `process.rs`: `cp1_advertised_flags_are_accepted_by_the_shipped_public_parsers`, `cp1_catalogue_covers_the_public_command_flag_and_schema_matrix`, `cp1_fleet_forms_separate_execution_from_read_only_candidates_and_plans`, `cp2_due_candidates_and_tick_reports_follow_the_recorded_world` and `cp2_fleet_source_failures_and_partial_fleets_preserve_reports` run the executing tick or list its flags (checked: 5 of 55 fail).
- `contracts/cli.v1.schema.json`: the engine and executing-tick shapes.
- The Python half of the start-up switch, which the spec retires ("the activation handover") but no ticket owns: `tools/install/engine/`, `tools/install/handover/`, `tools/install/pc_activation/`, `tools/install/install.py`'s `ENGINE_RUNTIME` and `HANDOVER_RUNTIME`, and `tools/release/build_products.py`'s engine and handover packaging (and their tests in `tools/release/`). This is a release-packaging change. **Not build-checked here.** Outside D4: ER6 leaves it for open plan change P2.

**Re-seed, never delete:** `b5_due_running_builder_is_idle_without_cloudroom_or_state` and `b5_r13_due_ignores_a_superseded_approval_at_the_same_head` test the kept `fleet due`, but set up their world with the executing tick (`w.tick()`). ER6 writes their state directly so they stay keepers.

**Keepers:** `tests/fleet/b2_planner.rs` (the planner); the 35 `b5_edges` and 4 `b5_public` tests that pass on `--dry-run`; `b5_due_empty_repository_is_silent_and_never_reads_cloudroom`; `tests/cli-agent` `cp2` tests for `fleet due`.

**Closes as not needed:** #643, #642, #518, #461, #189, and #516 (First hour's engine recovery wording; see "Not covered by any ticket").
**Must not close:** #664. It is a live bug in the kept `openwiz new --yes` (room-cli v152's spawn receipt), not engine code, although ER6's acceptance criterion lists it. See open plan change P3.
**Stays open:** #143 and #561 (planner rules `fleet due` still uses), #82 (the GitHub reads stay).

### ER6's failing tests

With ER2 and ER6's deletions applied (and `--dry-run` kept), these `tests/fleet` tests fail because they run the executing `fleet tick`. ER6 deletes each one and names its keeper or says its behaviour is gone, except the two it re-seeds.

- `b5_tick.rs` (22): `b5_1196_claude_limit_prints_one_restart_and_keeps_the_branch`, `b5_1196_near_labels_keep_default_and_unknown_providers_wait`, `b5_1196_only_positive_claude_limit_stops_can_restart`, `b5_1196_recorded_fallback_replacement_waits_for_a_reviewer`, `b5_1196_restart_needs_its_lock_and_a_saved_record_before_printing`, `b5_1196_reviews_follow_the_recorded_builder_family`, `b5_1196_small_ticket_uses_small_builder`, `b5_1196_unknown_builder_family_refuses_a_reviewer`, `b5_1330_claude_fallback_is_refused_without_consuming_the_restart`, `b5_concurrent_ticks_share_one_builder_start`, `b5_crash_after_dispatch_never_repeats_an_uncertain_start`, `b5_due_running_builder_is_idle_without_cloudroom_or_state` (re-seed), `b5_merge_requires_every_observed_gate_including_real_success`, `b5_missing_orchestrator_leaves_notification_due_and_no_completion_record`, `b5_pending_created_start_is_recovered_without_a_second_builder`, `b5_plain_tick_names_a_failed_action_and_stays_silent_on_success`, `b5_plain_tick_names_a_failed_recovery_outcome_without_repeating_it`, `b5_plain_tick_names_a_refused_or_uncertain_action`, `b5_pre_merge_authority_recheck_refuses_a_revoked_plan_approval`, `b5_pre_merge_base_recheck_refuses_a_move_after_authority_refresh`, `b5_r13_due_ignores_a_superseded_approval_at_the_same_head` (re-seed), `b5_synthetic_fleet_reaches_last_merge_without_duplicate_builders`
- `b5_edges.rs` (37) and `b5_public.rs` (12): every test that calls `w.tick()`, `run(&["fleet", "tick"])` or `run(&["fleet", "tick", "--json"])`. Run `cargo test -p openwiz-tests --test fleet` on ER6's branch to get the exact list.

## 8. ER5 (#799): what onboarding and install may stop calling

ER5 deletes nothing from the Rust code. Onboarding and install may stop calling:

- `openwiz engine preview`, `activate` and `status` (`skills/install/SKILL.md`, its removal steps, `tools/install/tests/journey/`)
- `openwiz fleet tick --dry-run --json` and `fleet tick --expect-plan PATH --json` (`skills/onboard/SKILL.md`, `skills/onboard/scripts/onboard.py`, `tools/install/tests/onboard/fake_openwiz.py`)

They may keep calling launch-fleet's frontier (`skills/launch-fleet/scripts/fleet.sh frontier`), `openwiz fleet <spec> --json`, `openwiz fleet due --github-only`, and the setup API.
**Path gap:** `tools/skills-eval/cases/in-approval-engine-preview.json` is an install-skill eval case that expects `engine activate`.

## 9. Infra MT9 (#828): live-smoke

live-smoke may stop calling `openwiz fleet tick --expect-plan` (`tools/live-smoke/restriction.py` and its tests), which ER6 deletes. `fleet tick --dry-run` stays (D1).

## Not covered by any ticket

- **The web view's engine step.** `GET /api/v1/setup` still returns an `engine` component ("No engine has been selected or activated."; `crates/server/src/setup.rs`, `crates/store/src/setup.rs`). The Setup page shows engine hosts (`apps/web/src/components/Setup.tsx`), and First hour says "Choose where the engine runs next" (`apps/web/src/components/FirstHour.tsx`; `contracts/setup.v1.md`, `contracts/first-hour.v1.md`). ER5 owns only the skills and `tools/install`, so user story 2 ("no engine choice during setup") stays unmet in the web view until a ticket owns these files.

## Left for later

Needed by nothing kept once the removals merge, and not named for retirement. Each stays.

| Module | Why it is left |
| --- | --- |
| `crates/service/src/events/` (webhook intake and relay) | A service job that routes GitHub hints to sends. Not named for retirement; it uses `tick::Sources` and the CLI's `Inventory` and `World` |
| `crates/service/src/scheduler.rs` tick helpers (`tick_monitor`, `restart_stalled_tick`, `restart_tick`, `register_tick`, `TickRunGuard`) and `tick.rs`'s `JOB`, `register_with`, `register_with_control` | Only health and its tests used them; the scheduler is out of scope (spec, "Out of Scope") |
| `crates/service/src/document.rs`, `state.rs` (tick, incident, watchdog and notification fields of the config and state documents) and `contracts/service.v1.schema.json` | The service's own document readers. No removal owns them, and old state files keep reading |
| `crates/adapters/cloudroom/src/loops.rs` | The health loop inventory. The Cloudroom adapter's reads are kept |
| `crates/adapters/github/src/writes.rs` | GitHub writes used by the executor and health records; still used by `crates/service/src/update.rs` |
| `crates/core/src/health/` remainder (`Id`, `Number`, `Repository`, `SeenLoop`, `is_openwiz_loop`) | Used by the kept adapters. A later move to a neutral module would empty `health` |
| `crates/core/src/notifications/model.rs` and `stock.rs` | Used by the ready stock and Decisions. The same move applies |
| `crates/service/src/update.rs`, `app.rs`, `runtime.rs`, `paths.rs` | The rest of `openwiz-service` (spec, "Out of Scope") |
| `crates/store/src/loops/paths.rs` `inspect_settled` | If ER4 does not delete it; #818 may use it |
| `crates/service/src/bootstrap.rs` | The packaged service's fail-closed start gate; it belongs to the rest of the service, kept for a later grill (D2). ER6 does not delete it |

## Decisions

The orchestrator's ruling on ER1's questions, 2026-11-15 (#795 comment 6903517854), following this map's recommendations:

- **D1 (Q2):** `fleet tick --dry-run` is a kept read. ER6 retires only the executing `fleet tick` and `--expect-plan`.
- **D2 (Q3):** `crates/service/src/bootstrap.rs` stays. It belongs to the rest of the service, which stays for a later grill.
- **D3 (Q4):** ER4 may edit `tests/web-api/a4_no_mutation.rs`, `tests/web-api/contract.rs` and `tests/loops/l6_api.rs`, only to remove the notification routes.
- **D4 (Q7):** each removal has a narrow grant, same intent, for exactly the path gaps this map lists for it. Each pull request lists the ones it uses.

## Open plan changes

These change #786's graph or ticket bodies, so they go to Jake as one proposed revision 4 of the plan. None blocks ER1. Until it is approved, each ticket keeps its current body.

- **P1 (Q1):** a new real link, ER6 (#800) blocked by ER2 (#796). ER6 deletes the executor that ER2's scheduled tick calls (section 7, "Order").
- **P2 (Q5):** a new ticket for the Python engine, handover and activation runtimes (`tools/install/engine/`, `handover/`, `pc_activation/`) and their release packaging (`tools/install/install.py`, `tools/release/build_products.py`). It is listed in ER6's path gaps but outside D4: ER6 leaves it.
- **P3 (Q6):** a shorter close list for ER6: #664 stays open (a live bug in the kept `openwiz new --yes`).
- **P4:** a new ticket for the web view's Setup and First-hour engine step ("Not covered by any ticket").

## The build check (E1)

Run on scratch worktrees of `192f6e4` (ER3's revised section: `3228599`), nothing committed, Rust 1.99.1 and Node 24.22.1.

| Variant | `cargo check --workspace --all-targets` | `cargo clippy --workspace --all-targets -- -D warnings` | Tests run |
| --- | --- | --- | --- |
| ER2 alone | pass, no warnings | pass | none needed (all deleted files were tests or the executor composition) |
| ER3 alone (revised: watchdog-only health job) | pass | pass | `openwiz-service`: `l5b-watchdog` 12/12 (harness adapted, assertions unchanged), `l5-watchdog` 7/7, `l12-registration` 17/17, `l3-runner` 58/58, `l10-approval` 15/15, `l11-limits` 14/14, `notifications-engine` 33/33, `notifications-delivery` 5/5, `t4-unit` 9/9, `t4-service` 21/21, `t6-update` 46/46, lib 13/13; `checks` 145/145 |
| ER4 alone | pass | pass | `web-api` 354/354 (after the route-catalogue edits; 347/354 before); `checks` 145/145; `notifications` (stock only) 7/7; `loops` `l6_api` 9/9 (after its edit); unit tests of core, store, server and service pass; `apps/web` `typecheck`, `check` and `build` pass |
| ER6 alone on `main` | **fails**: `crates/service/src/tick.rs` needs the executor (P1) | none | none |
| ER6 after ER2 | pass | pass | `proof` 125/125; `fleet` 216 pass, 71 fail (the list above); `cli-agent` 50 pass, 5 fail (the path gap above) |
| ER2, ER3 (revised), ER4 and ER6 together | pass, no warnings | pass | see "The combined build" below |

On `main` itself, `loops`'s `l6_config::real_cli_uses_install_operator_and_refuses_unconfigured_or_caller_identity`
also fails unless `openwiz` is built first (its own message says so). It is unrelated to this map.

### The combined build (R6)

The four current lists together: ER2, ER3 keeping the loop watchdog (section 4), ER4 and ER6, with `fleet tick --dry-run` kept (D1).

- **Base:** `main` at `c51c009`. `main` has changed nothing under `crates/` or `tests/` since `3228599`, where ER3's section was checked.
- **Map revision:** this file at PR #855 head `e50631f` (sections 4 to 7 unchanged since).
- **How:** a scratch worktree, nothing committed. The scratch changes were applied in this order: ER3's revised cut, then ER2 and ER6, then ER4. The two overlaps were resolved as the map says. In `crates/service/src/runtime.rs`, ER3's `register(&mut scheduler, now)` stays and ER4's notification job goes. In `crates/store/src/loops/paths.rs`, `inspect_settled` goes. Then `cargo fmt`. Result: 109 files changed, 89 insertions, 29,182 deletions.
- **Build:**
  - `cargo check --workspace --all-targets`: pass, no warnings.
  - `cargo clippy --workspace --all-targets -- -D warnings`: pass.
  - `cargo fmt --check`: pass.
  - In `apps/web`, `npm ci --ignore-scripts`, `npm run typecheck`, `npm run check` and `npm run build` all pass.
- **Scoped tests run, `openwiz-service` only:**
  - Pass: lib 13/13, `l10-approval` 15/15, `l11-limits` 14/14, `l3-runner` 58/58, `l4-events` 25/25, `l4b-intake` 24/24, `l5-watchdog` 7/7, `l5b-watchdog` 12/12, `l6-switches` 10/10, `t4-paths` 1/1, `t4-scheduler` 7/7, `t4-service` 19/19, `t4-unit` 9/9, `t6-update` 46/46, `t7-app` 15/15.
  - Two found in this run:
    - `l12-registration` failed 3 of 17. These three tests wait for `status["tick"]["last_ended"]`, which never comes once ER2 removes the scheduled tick; the watchdog-only pass did complete. This is polish #867 (R4): ER2 drops that one wait. With it dropped: 17/17.
    - `t4-reader` failed 1 of 3. Its cases `health_pass_must_include_a_tick_result` and `state_reader_requires_cloudroom_as_the_first_health_result` test the S1 rules ER3 relaxes (section 4, `document.rs`). ER3 deletes those two cases along with the rules (`tests/service/t4_reader.rs`, same intent as D4). With them deleted: 3/3. Clippy passes again with both edits.
- **Not run locally:** the other test targets (`docs/agents/fleet.md`: never the full workspace or browser suites locally). CI runs the full set on each removal's pull request. ER6's own test changes (section 7) were not applied, so `fleet` and `cli-agent` would still fail as that section lists.
