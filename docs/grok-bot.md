# Grok Bot + OpenWiz

Grok Bot is xAI's always-on assistant, with its own cloud computer. This page shows how a Grok Bot user adds the OpenWiz skills, asks a first question and runs a first fleet. It also says what works today and what comes later.

**Status:** not yet tried end to end on a real Grok Bot. The steps follow Grok Bot's own docs and the directory's code.

## What you get

- The OpenWiz skills inside your Bot, for the talking side of the work: grill an idea, plan it into a spec and tickets, research a question, ask where things stand.
- Your Bot reads and writes your GitHub repository through Grok Bot's GitHub app.
- Builders still run the normal way, from your coding agent on your computer. Your Bot can plan and watch them through GitHub.

## Before you start

- A plan that includes Grok Bot: The X Subscription Premium ($30 a month) or higher. See [Grok Bot's docs](https://docs.x.ai/grok-bot).
- The Grok Bot app for desktop or mobile, from [x.ai/bot](https://x.ai/bot).
- One GitHub repository to try it on. A new private demo repository is fine.

## Steps

Every sign-in and connection below is your own click. OpenWiz never touches a login.

1. **Install the app and sign in.** Open the Grok Bot app and choose Sign in. Finish in the browser.
2. **Connect GitHub to just your repository.** Add Grok Bot's GitHub app and allow only the one repository you chose.
3. **Add the OpenWiz app.** Go to [grok-bot.directory](https://grok-bot.directory), search for OpenWiz and choose **Add to Grok Bot**. This sends a ready message that has your Bot save each OpenWiz skill.
4. **Have the Bot clone the skills.** The skills run scripts that sit beside each skill file, and step 3 saves only the text. So ask your Bot:

   > On your computer, run `git clone --depth 1 --branch v0.1.2 https://github.com/openwizdev/WizSkills`, and read OpenWiz skills from that folder.

   A terminal command may stop on an **Allow / Skip** card. Allow it only if it is that command. This step is not yet tried on a real Grok Bot.
5. **Ask a first question.** For example:

   > Use the grill skill on: a small idea for my repository

   Or ask "Use ask-wiz: what should I do first?"

## Run a first fleet

Today a fleet starts from your computer, not from Grok Bot. In Claude Code or Codex, paste:

> Install OpenWiz from github.com/openwizdev/OpenWiz

Then follow [Install OpenWiz](install.md) and [Your first hour](first-hour.md). The fleet runs on CloudRoom. Your Bot can follow it through the same GitHub issues and pull requests, for example "Use where-are-we on my repository".

## What works today, in 0.1.1 and later

| When | What | Status |
| --- | --- | --- |
| Today | Skills in Grok Bot for talking work: grill, plan-graph, research, where-are-we, ask-wiz | Expected to work; not yet tried end to end |
| Today | A first fleet from Claude Code or Codex, watched by your Bot through GitHub | The normal install path |
| 0.1.1 | Grok Bot as the orchestrator that starts builders ([#1396](https://github.com/openwizdev/OpenWiz/issues/1396)) | Planned; not proven |
| Later | Grok Bot as a builder that OpenWiz starts, wakes and stops | Not planned for 0.1.x: Grok Bot has no way to address or stop one run |

## Safety

- **Never paste a key or token into the chat.** Use Grok Bot's own secret prompt if a tool needs one.
- **The Bot acts as your GitHub account.** Its comments and pull requests show as you. Connect it only to the repository you want it to touch.
- **It never posts to X** unless you add the X plugin yourself.
- **You can stop it.** Remove the OpenWiz skills, or remove the repository from the GitHub app, at any time.
