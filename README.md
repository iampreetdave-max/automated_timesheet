# Automated Timesheet

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-4A154B?style=flat&logo=slack&logoColor=white)
![Claude API](https://img.shields.io/badge/Claude_API-Anthropic-orange?style=flat)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=githubactions&logoColor=white)

> Automatically generates daily timesheet entries from Slack conversations using Claude AI, with approval via emoji reactions.

## About

Automated Timesheet is a GitHub Actions-powered bot that reads your daily Slack messages, uses the Claude API to extract work activities into a professional summary, DMs you the summary for approval, and saves it to a SharePoint timesheet upon confirmation. The approval flow uses Slack emoji reactions — the bot adds a checkmark, and you react to confirm.

## Tech Stack

- **Language:** Python 3
- **AI:** Claude API (Anthropic)
- **Messaging:** Slack API (Bot + User tokens)
- **Storage:** Microsoft SharePoint (via Graph API)
- **Automation:** GitHub Actions (scheduled cron)

## Features

- **Daily Slack scanning** — fetches all messages from a channel for the current day
- **AI task extraction** — Claude analyzes conversations and extracts professional work summaries
- **DM approval flow** — bot sends summary via DM with a checkmark reaction for approval
- **Reaction-based confirmation** — react with your own checkmark to approve and save
- **SharePoint integration** — approved summaries are saved to a SharePoint timesheet
- **3-hour approval window** — automatic timeout for pending approvals
- **GitHub Actions automation** — runs daily at 10 PM via cron schedule

## Getting Started

### Prerequisites

- Slack Bot Token (`xoxb-...`) and User Token (`xoxp-...`)
- Anthropic API key
- Microsoft Graph API credentials (for SharePoint)
- GitHub repository with Actions enabled

### Environment Variables

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_USER_TOKEN=xoxp-...
ANTHROPIC_API_KEY=sk-ant-...
SLACK_CHANNEL_ID=C0AB...
MY_SLACK_USER_ID=U09P...
```

### Run

**Generate daily summary:**

```bash
python daily_summary.py
```

**Check for approval reaction:**

```bash
python check_reaction.py
```

**Get SharePoint IDs:**

```bash
python get_sharepoint_ids.py
```

## How It Works

1. **Fetch:** `daily_summary.py` pulls today's Slack messages from the configured channel
2. **Extract:** Sends the conversation to Claude API to identify real work activities
3. **Notify:** Bot DMs you a professional task summary with a checkmark reaction
4. **Approve:** You react with your own checkmark to confirm the summary
5. **Save:** `check_reaction.py` detects your reaction and saves the entry to SharePoint

## Project Structure

```
automated_timesheet/
├── daily_summary.py       # Main: fetch messages, extract tasks, send DM
├── check_reaction.py      # Check for approval reaction, save to SharePoint
├── get_sharepoint_ids.py  # Utility to discover SharePoint site/list IDs
├── .github/               # GitHub Actions workflow configs
└── README.md
```

## License

This project is open source.
