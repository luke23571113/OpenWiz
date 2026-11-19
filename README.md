<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/openwiz-lockup-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs/brand/openwiz-lockup-light.svg">
    <img alt="OpenWiz" src="docs/brand/openwiz-lockup-light.svg" width="380">
  </picture>
</h1>

OpenWiz runs coding agents in fleets: you approve a plan, and OpenWiz's agents build, review and merge its tickets. The app lives at [openwiz.dev/app](https://openwiz.dev/app); this repository is the `openwiz` command, its adapters and the engine. The [org map](https://github.com/openwizdev) shows how it fits with the other repositories.

## Install

Paste this line into your coding agent:

> Install OpenWiz from github.com/openwizdev/OpenWiz

Agents: read [`skills/install/SKILL.md`](https://github.com/openwizdev/WizSkills/blob/v0.1.2/skills/install/SKILL.md) and follow it. It checks the machine and CloudRoom, installs the verified prebuilt release (no Rust or Node), opens setup, then hands the first fleet to the [`onboard`](https://github.com/openwizdev/WizSkills/blob/v0.1.2/skills/onboard/SKILL.md) skill. Nothing starts until the user approves a plan. People: see the [install guide](docs/install.md), including recovery and removal. OpenWiz is free now. Paid plans come later. CloudRoom and model charges are separate and not included.

## Versions

What each version adds is in [CHANGELOG.md](CHANGELOG.md). A version has at most five outcomes, each one something a user can see or check, and claims nothing its evidence doesn't show; tests alone never prove live behaviour. A version number says when something changed, not what works with what.

## Contributing

Agents start at [AGENTS.md](AGENTS.md); the build runs with `cargo test --workspace` on Rust 1.99.1. For anything beyond a small fix, open an issue first. Everything you post is public: use synthetic examples only (`example.com`, "User A"), and no personal data, secrets, transcripts or private links. A new dependency needs the maintainer's approval.

OpenWiz is licensed under the [Apache License 2.0](LICENSE). Unless you state otherwise, a contribution you submit is licensed under the same terms (section 5 of the license); there is no separate contributor agreement.
