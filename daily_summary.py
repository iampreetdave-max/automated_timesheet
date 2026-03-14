"""
daily_summary.py
Runs at 10pm daily via GitHub Actions.
1. Fetches today's messages from Slack channel
2. Sends to Claude API to extract work tasks
3. DMs you the summary on Slack
4. Bot adds ✅ reaction to the summary message
5. Saves message timestamp to a file for check_reaction.py to pick up
"""

import os
import json
import time
import datetime
import requests

# ── Config (loaded from env) ────────────────────────────────────────────────
SLACK_BOT_TOKEN   = os.environ["SLACK_BOT_TOKEN"]        # Bot token (xoxb-...)
SLACK_USER_TOKEN  = os.environ["SLACK_USER_TOKEN"]       # User token (xoxp-...) for reading channel history
CHANNEL_ID        = os.environ.get("SLACK_CHANNEL_ID", "C0AB46ZQA4D")
MY_SLACK_USER_ID  = os.environ.get("MY_SLACK_USER_ID",  "U09PKNWGCJF")
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

STATE_FILE = "reaction_state.json"   # persisted via GH Actions artifact / cache


def get_today_timestamps():
    """Return Unix timestamps for start and end of today (UTC)."""
    now   = datetime.datetime.utcnow()
    start = datetime.datetime(now.year, now.month, now.day, 0, 0, 0)
    end   = datetime.datetime(now.year, now.month, now.day, 23, 59, 59)
    return str(start.timestamp()), str(end.timestamp())


def fetch_today_messages():
    """Fetch all messages from the channel posted today."""
    oldest, latest = get_today_timestamps()
    messages = []
    cursor   = None

    while True:
        params = {
            "channel": CHANNEL_ID,
            "oldest":  oldest,
            "latest":  latest,
            "limit":   200,
        }
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {SLACK_USER_TOKEN}"},
            params=params,
            timeout=30,
        )
        data = resp.json()

        if not data.get("ok"):
            raise RuntimeError(f"Slack history error: {data.get('error')}")

        messages.extend(data.get("messages", []))

        # Handle pagination
        meta = data.get("response_metadata", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break

    return messages


def build_conversation_text(messages):
    """Convert messages list into a plain-text transcript."""
    lines = []
    for msg in reversed(messages):   # oldest first
        user = msg.get("user", "unknown")
        text = msg.get("text", "").strip()
        if text:
            lines.append(f"{user}: {text}")
    return "\n".join(lines)


def extract_tasks_with_claude(conversation: str) -> str:
    """Call Claude API to extract work tasks from the conversation."""
    prompt = f"""You will receive a Slack conversation transcript. Each message has a sender ID.

Your goal is to extract work activities performed by the user with ID "{MY_SLACK_USER_ID}" and convert them into a professional timesheet activity summary.

STEP 1 - TASK DETECTION: Identify messages by user "{MY_SLACK_USER_ID}". Extract ONLY real work performed. Ignore casual chat, greetings, jokes, acknowledgements, brainstorming, suggestions. Only keep: testing, reviewing, implementing, validating, debugging, documenting, updating, configuring, analyzing, deploying, reporting.

STEP 2 - CONSOLIDATION: Combine related micro-actions. Remove duplicates. Limit to 4-8 activities max.

STEP 3 - FORMAT: Output ONE single paragraph. Separate each activity with " - ". NO bullet points, NO line breaks, NO dashes at the start. Past-tense action verbs. Professional.

Example output:
Performed QA testing on filter functionality - Validated frontend behavior against backend records - Documented identified discrepancies - Coordinated with development team regarding fixes

If no valid work activities are found, return exactly: NO_TASKS_FOUND

Conversation:
{conversation}"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        json={
            "model":      "claude-opus-4-5",
            "max_tokens": 1024,
            "messages":   [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"].strip()


def open_dm_channel(user_id: str) -> str:
    """Open (or retrieve) a DM channel with a user. Returns channel ID."""
    resp = requests.post(
        "https://slack.com/api/conversations.open",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type":  "application/json",
        },
        json={"users": user_id},
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"conversations.open error: {data.get('error')}")
    return data["channel"]["id"]


def send_slack_dm(dm_channel: str, task_summary: str) -> str:
    """Send the summary as a DM. Returns the message timestamp (ts)."""
    today = datetime.datetime.utcnow().strftime("%m/%d/%Y")
    text  = (
        f"📋 *Task Summary for Approval* — {today}\n"
        f"{task_summary}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot has added a ✅ below. *React with your own ✅ to confirm and save to timesheet.*\n"
        f"_(You have 3 hours to react)_"
    )
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type":  "application/json",
        },
        json={
            "channel": dm_channel,
            "text":    text,
            "mrkdwn":  True,
        },
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"chat.postMessage error: {data.get('error')}")
    return data["message"]["ts"]


def add_bot_reaction(channel: str, ts: str):
    """Add ✅ reaction from the bot to the summary message."""
    resp = requests.post(
        "https://slack.com/api/reactions.add",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type":  "application/json",
        },
        json={
            "channel": channel,
            "timestamp": ts,
            "name":    "white_check_mark",
        },
        timeout=15,
    )
    data = resp.json()
    # already_reacted is fine — idempotent
    if not data.get("ok") and data.get("error") != "already_reacted":
        raise RuntimeError(f"reactions.add error: {data.get('error')}")


def save_state(channel: str, ts: str, task_summary: str):
    """Persist the message info so check_reaction.py can pick it up."""
    today = datetime.datetime.utcnow().strftime("%m/%d/%y")
    state = {
        "channel":      channel,
        "ts":           ts,
        "task_summary": task_summary,
        "date":         today,
        "saved":        False,
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"State saved to {STATE_FILE}")


def main():
    print("=== Daily Summary Script ===")

    # 1. Fetch today's messages
    print("Fetching today's Slack messages...")
    messages = fetch_today_messages()
    print(f"  Found {len(messages)} messages")

    if not messages:
        print("No messages today. Exiting.")
        return

    conversation = build_conversation_text(messages)

    # 2. Extract tasks via Claude
    print("Calling Claude API to extract tasks...")
    task_summary = extract_tasks_with_claude(conversation)
    print(f"  Summary: {task_summary[:120]}...")

    if task_summary == "NO_TASKS_FOUND":
        print("Claude found no work tasks today. Exiting.")
        return

    # 3. Open DM channel & send message
    print("Sending DM to Slack...")
    dm_channel = open_dm_channel(MY_SLACK_USER_ID)
    ts         = send_slack_dm(dm_channel, task_summary)
    print(f"  Message sent. ts={ts}")

    # 4. Add bot ✅ reaction
    print("Adding bot ✅ reaction...")
    time.sleep(1)   # small delay to avoid rate limits
    add_bot_reaction(dm_channel, ts)
    print("  Reaction added.")

    # 5. Save state for check_reaction.py
    save_state(dm_channel, ts, task_summary)
    print("Done! Waiting for your ✅ reaction to save to timesheet.")


if __name__ == "__main__":
    main()
