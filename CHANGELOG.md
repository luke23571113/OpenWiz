# Changelog

All OpenWiz versions, newest first. How versions work: [RELEASING.md](https://github.com/openwizdev/OpenWiz/blob/main/RELEASING.md).

## 0.0.12 · 2026-11-16

**Scripts and agents can drive OpenWiz**

**What's new for you**

- Run `openwiz help --agent` to get every command, option and result format in one list. It reads nothing and changes nothing.
- Add `--json` to any command for one clean result, and a clear error when something goes wrong.

Live-checked in this release's smoke test, run by agents: installing this release, `openwiz help --agent`, `ls --json` and `show --json`, one send to a throwaway thread, and one new thread in a throwaway project. Everything else here is tested on synthetic fixtures only; the terminal app was never live-checked on a Mac.

**Under the hood**

- Every `--json` command prints exactly one document, its result or a structured error, and the command list is a written contract.
- Fleet candidate checks can return JSON too.
- A visual terminal app (`openwiz ui`) was built in this version and is being retired.

[Full release on GitHub](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12)

## 0.0.11 · 2026-11-16

**Make every decision in one place, and see the whole plan**

**What's new for you**

- A Decisions page: answer grill questions, confirm specs and approve plans. Each answer goes to your orchestrator as one message.
- Anything live, release or publishing asks you twice before it goes.
- A Plan page shows each version's tickets by state, what holds up the most work, and what any ticket waits on.

Tested on synthetic fixtures only; a whole day of real decisions on these pages is still unverified.

**Under the hood**

- A plan API reports ticket states, dependencies and the critical chain, and marks reads that failed instead of hiding them.
- The planning skills now ask for decisions in a fixed, structured form.
- Each answer is sent with the question and revision it answers, and its text is kept exactly.
- Malformed decision requests are reported, not dropped.

[Full release on GitHub](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12)

## 0.0.10 · 2026-11-16

**A cockpit for your phone and PC**

**What's new for you**

- A Cockpit page: what needs you, oldest first, and every running agent by project and fleet.
- Answer an item right there when its exact proposal is known, after a preview and a confirm. Risky ones ask twice.
- A command bar to move around fast: `ls`, `cd`, `next`, `blockers`, or an item's number.
- Each item shows its question, a link, when it was asked and how risky it is.

Tested on synthetic fixtures only; the cockpit on a real phone and PC is still unverified.

**Under the hood**

- The local server answers the whole cockpit in one read-only request, and marks any part it couldn't read or that is stale, instead of showing it empty.
- `openwiz fleet` shows the same details as the page.

[Full release on GitHub](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12)

## 0.0.9 · 2026-11-16

**All your loops in one place**

**What's new for you**

- A Loops page on your PC lists every scheduled job: next run, last run and cost over the last day, problems first.
- Switch any loop off or on. It records who did it and when, and stays that way after a restart.
- No 100-loop limit: tests plan 200 loops within the shared limits.
- OpenWiz tells you when a loop check is missed or stuck, and stays quiet until that changes.

Tested on synthetic fixtures only; a whole day of real loops run from the phone is still unverified.

**Under the hood**

- The service runs loop checks itself, and never retries an agent start whose result is unclear.
- Review and CI follow-ups go to the agent already on that work, through durable records; GitHub webhook events are routed once each.
- A loop runs only when its exact definition is approved and it has its own capacity limits; other service work carries on.
- Loop health is watched separately from the scheduler.

[Full release on GitHub](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12)

## 0.0.8 · 2026-11-16

**OpenWiz keeps running on your PC**

**What's new for you**

- `openwiz-service` runs on your PC: it serves the web page, runs scheduled jobs and reports its own status.
- It checks its own health and recovers its loops, fleet runs and the web server when they fail.
- It updates itself from tested builds, and goes back to the last good one if a new one won't start.

Tested on synthetic fixtures only; a whole day with the Mac shut is still unverified.

**Under the hood**

- A GitHub App gives the service tokens scoped to each repository, renewed and shared across its jobs; the private key stays in owner-only storage.
- The service runs the fleet tick on a schedule and records how each run ended.
- The tick picks builders by ticket label and reviewers from the other model family, with one fallback that keeps the branch when a Claude usage limit stops a builder.
- A service update can resend a record that never went out.

[Full release on GitHub](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12)

## 0.0.7 · 2026-11-16

**Helpers for builders and reviewers, and a "where are we?" report**

**What's new for you**

- Builders and reviewers can bring in helpers for side jobs, while the lead keeps every decision.
- Ask "where are we?" and get one screen of current work, open decisions and the next move.
- New skills to map an unclear project (wayfind), research with cited sources (research), and track down a hard bug before fixing it (diagnose).

Helper swarms ran for real and "where are we?" was used for real; whether helpers make work faster or cheaper is still unproven.

**Under the hood**

- A written guide sets how many helpers to use and which ones.
- A check catches a helper that pushes code; helpers never push.
- The skills check now covers the new skills.

[Full release on GitHub](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12)

## 0.0.6 · 2026-11-16

**Fleets run inside OpenWiz**

**What's new for you**

- `openwiz fleet tick` moves your fleets forward: it works out what is due and does it.
- `openwiz fleet due --github-only` tells a loop whether there may be work for it.
- See your fleets with `openwiz fleets` and on the web page's fleets screen.

Tested on synthetic fixtures only; a real fleet run by OpenWiz itself, followed on a phone, is still unverified.

**Under the hood**

- Fleet views refuse conflicting GitHub facts and show "unknown" instead of guessing progress or who is building.
- Larger fleet lists finish within the time budget: merge history is read in batches.
- Inventory commands report a failed write, and send previews refuse thread details with repeated keys.
- On a PC, OpenWiz finds the running CloudRoom app, and asks you to restart CloudRoom if an update leaves two copies running.
- Keyboard focus stays put while pages load and fleets refresh.

[Full release on GitHub](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12)

## 0.0.5 · 2026-11-05

**Fleets of agents build for you**

**What's new for you**

- Eight skills for coding agents: they grill you on an idea, plan it into tickets, then build, review and merge each one.
- Use them in Claude Code as a plugin, or in Codex straight from the repo.
- Nothing merges without an independent review of the exact code and green CI.

Tested with the skills' static checks, and live: a real fleet used these skills to build 0.0.6.

**Under the hood**

- The skills are plain Markdown files any agent can follow; GitHub keeps the specs, tickets, reviews and decisions.
- Each ticket gets one builder, and each pull request a reviewer from a different model family.
- A static check in CI keeps the skill set, links and plugin manifest in step.

## 0.0.4 · 2026-11-05

**Start new threads, with files**

**What's new for you**

- `openwiz new` starts a Cloud thread in one of your projects. It shows exactly what it will do first, and creates it only with `--yes`.
- Attach files and images to a new thread or a queued message, from the terminal or the web page.
- One thread per create: if the result is unclear, it tells you instead of trying again.

Tested on fixtures; the live check of new threads and attachments is still open.

**Under the hood**

- New threads reuse the same local store and text rules as sending, with no new dependencies.
- New write routes follow the same security rules as sending.

## 0.0.3 · 2026-11-05

**Message your threads**

**What's new for you**

- `openwiz send` sends one message to a thread, as Queue or Steer.
- Or send from the web page on your phone.
- If a send's result is unclear, OpenWiz says so instead of sending twice.

Tested on fixtures and in a live check on test threads; it was accepted with some gaps still recorded.

**Under the hood**

- The terminal and the web page share one record of each send.
- A read-only preview works out what a send will do before you press it.

## 0.0.2 · 2026-10-30

**Your threads on your phone**

**What's new for you**

- A private web page served from your own computer: your threads by project, with status and age. Tap one for details.
- Open it from anywhere through a Cloudflare Tunnel, with a login only your email can use.
- It only reads, and it tells you when data is stale or you're signed out.

Tested on fixtures, and the owner-only login was checked live; the full check on a Mac and a phone is still open.

**Under the hood**

- A local Rust server serves the API and a Next.js web app.
- Cloudflare Access checks your login, and the tunnel checks it again at your computer.

## 0.0.1 · 2026-10-30

**Your CloudRoom threads in the terminal**

**What's new for you**

- `openwiz ls` lists your threads with status, project and age; `-l` adds a recap, model and effort.
- `openwiz show <id>` shows one thread and its final output.
- `--json` for scripts. It only reads: it never changes a thread.

Tested on fixtures and in a live check on a real Mac.

**Under the hood**

- A Rust command-line tool that reads through your existing, signed-in `room-cli`.
- The `room-cli` version is recorded, never required.

## 0.0.0 · 2026-10-22

**The design, before any code**

**What's new for you**

- The plan for OpenWiz: what it does, how it is built and how it is released. No code yet.
- Published first as OpenFleet, and renamed OpenWiz before 0.0.1.

Nothing to test yet: this version is documents only.

**Under the hood**

- With the rename, the stack was chosen: one Rust core owns state, permissions and coordination; the CLI is Rust and the web client is Next.js and TypeScript, in one repository.
- Architecture diagrams, release rules and a draft protocol spec (PACP v0.1).
- Licensed under Apache 2.0.
