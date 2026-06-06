# Automated Timesheet

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-4A154B?style=flat&logo=slack&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=githubactions&logoColor=white)

A GitHub Actions bot that turns each day's Slack activity into a professional timesheet entry, approved by an emoji reaction and saved to SharePoint.

## Overview

Automated Timesheet reads your daily Slack channel history, uses the Anthropic Claude API to distill it into a concise, professional activity summary, and DMs that summary to you for approval. You confirm by reacting with a checkmark; a second scheduled job detects the reaction and writes the approved entry to a SharePoint list via the Microsoft Graph API. The whole flow runs unattended on a daily GitHub Actions cron schedule.

## Key Features

- **Daily Slack scanning** — paginates through the configured channel's history for the current day
- **AI task extraction** — Claude filters out chatter and consolidates real work into a single professional, past-tense summary (4–8 activities)
- **DM approval flow** — the bot DMs you the summary and adds a checkmark reaction
- **Reaction-based confirmation** — you react with your own checkmark to approve; nothing is saved without it
- **SharePoint storage** — approved entries are written to a SharePoint list through the Microsoft Graph API
- **State handoff between jobs** — `daily_summary.py` persists message details to `reaction_state.json` for `check_reaction.py` to pick up
- **Scheduled automation** — runs daily via GitHub Actions cron

## How It Works

1. **Fetch** — `daily_summary.py` pulls today's Slack messages from the configured channel (using a user token for channel history).
2. **Extract** — the transcript is sent to the Claude API, which returns a one-paragraph activity summary (or `NO_TASKS_FOUND`).
3. **Notify** — the bot opens a DM, posts the summary, and adds a checkmark reaction; message details are saved to `reaction_state.json`.
4. **Approve** — you react to the DM with your own checkmark within the approval window.
5. **Save** — `check_reaction.py` detects the reaction and writes the entry to SharePoint via Microsoft Graph.

## Tech Stack

- **Language:** Python 3 (`requests`)
- **AI:** Anthropic Claude API
- **Messaging:** Slack Web API (bot and user tokens)
- **Storage:** Microsoft SharePoint via the Graph API
- **Automation:** GitHub Actions (scheduled cron)

## Getting Started

### Prerequisites

- A Slack bot token (`xoxb-...`) and user token (`xoxp-...`)
- An Anthropic API key
- Microsoft Graph API credentials with access to the target SharePoint site/list
- A GitHub repository with Actions enabled

### Environment variables

Provide these as environment variables (e.g. GitHub Actions secrets) — never commit real values:

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Bot token (`xoxb-...`) for posting DMs and reactions |
| `SLACK_USER_TOKEN` | User token (`xoxp-...`) for reading channel history |
| `ANTHROPIC_API_KEY` | Anthropic API key for the summary generation |
| `SLACK_CHANNEL_ID` | Channel to scan for daily messages |
| `MY_SLACK_USER_ID` | Your Slack user ID (whose work is summarized and who approves) |

SharePoint/Graph credentials are additionally required by the save step. Use `get_sharepoint_ids.py` to discover the relevant SharePoint site and list IDs.

### Run

```bash
python daily_summary.py    # Fetch messages, extract tasks, DM the summary for approval
python check_reaction.py   # Detect the approval reaction and save to SharePoint
python get_sharepoint_ids.py  # Utility: discover SharePoint site/list IDs
```

In production these run on a daily GitHub Actions schedule rather than by hand.

## Project Structure

```
automated_timesheet/
├── daily_summary.py        # Fetch Slack messages, extract tasks via Claude, DM for approval
├── check_reaction.py       # Detect the approval reaction and save to SharePoint
├── get_sharepoint_ids.py   # Utility to discover SharePoint site/list IDs
├── reaction_state.json     # Runtime state handed off between the two jobs
└── .github/                # GitHub Actions workflow(s)
```
