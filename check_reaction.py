"""
check_reaction.py
Runs every 15 minutes via GitHub Actions.
1. Reads reaction_state.json (written by daily_summary.py)
2. Checks if the ✅ reaction count >= 2 (bot + you)
3. If yes → finds today's row in Excel (SharePoint) and updates column C
4. Sends a confirmation DM
5. Marks state as saved so it doesn't run again
"""

import os
import json
import datetime
import requests

# ── Config ──────────────────────────────────────────────────────────────────
SLACK_BOT_TOKEN    = os.environ["SLACK_BOT_TOKEN"]
SLACK_USER_TOKEN   = os.environ["SLACK_USER_TOKEN"]
MY_SLACK_USER_ID   = os.environ.get("MY_SLACK_USER_ID", "U09PKNWGCJF")
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]   # not used here but kept for parity

# Microsoft Graph / SharePoint
MS_CLIENT_ID       = os.environ["MS_CLIENT_ID"]
MS_CLIENT_SECRET   = os.environ["MS_CLIENT_SECRET"]
MS_TENANT_ID       = os.environ["MS_TENANT_ID"]

# SharePoint file identifiers — set these in GitHub Secrets
# SHAREPOINT_SITE_ID  example: agilitytech1-my.sharepoint.com,<site-guid>,<web-guid>
# SHAREPOINT_DRIVE_ID example: b!<drive-guid>
# SHAREPOINT_ITEM_ID  example: <item-guid>
# SHEET_NAME          example: preet   (the worksheet tab name)
SHAREPOINT_SITE_ID  = os.environ["SHAREPOINT_SITE_ID"]
SHAREPOINT_DRIVE_ID = os.environ["SHAREPOINT_DRIVE_ID"]
SHAREPOINT_ITEM_ID  = os.environ["SHAREPOINT_ITEM_ID"]
SHEET_NAME          = os.environ.get("SHEET_NAME", "preet")

STATE_FILE = "reaction_state.json"


# ── Microsoft Graph helpers ──────────────────────────────────────────────────

def get_ms_token() -> str:
    """Get an OAuth2 access token from Microsoft using client credentials."""
    url  = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     MS_CLIENT_ID,
        "client_secret": MS_CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_worksheet_range(token: str, cell_range: str = "A:C") -> list:
    """Read a range from the Excel worksheet. Returns list of rows (each row is a list)."""
    url = (
        f"https://graph.microsoft.com/v1.0"
        f"/drives/{SHAREPOINT_DRIVE_ID}"
        f"/items/{SHAREPOINT_ITEM_ID}"
        f"/workbook/worksheets/{SHEET_NAME}"
        f"/range(address='{cell_range}')"
    )
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("values", [])


def update_cell(token: str, cell_address: str, value: str):
    """Update a single cell in the Excel worksheet."""
    url = (
        f"https://graph.microsoft.com/v1.0"
        f"/drives/{SHAREPOINT_DRIVE_ID}"
        f"/items/{SHAREPOINT_ITEM_ID}"
        f"/workbook/worksheets/{SHEET_NAME}"
        f"/range(address='{cell_address}')"
    )
    resp = requests.patch(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json={"values": [[value]]},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"  Updated cell {cell_address} successfully.")


def find_row_for_today(rows: list, today_str: str) -> int | None:
    """
    Find the 1-based row index (Excel row number) matching today's date.
    today_str is in mm/dd/yy format (e.g. '03/13/26').
    Column A (index 0) contains dates.
    Row 1 is the header, so Excel rows start at 2.
    """
    # Also try mm/dd/yyyy format since Excel sometimes stores full year
    dt = datetime.datetime.strptime(today_str, "%m/%d/%y")
    date_variants = {
        today_str,
        dt.strftime("%-m/%-d/%y"),    # without leading zeros
        dt.strftime("%m/%d/%Y"),      # full year with leading zeros
        dt.strftime("%-m/%-d/%Y"),    # full year without leading zeros
        dt.strftime("%m/%d/%y"),      # original format
    }

    for i, row in enumerate(rows):
        cell_value = str(row[0]).strip() if row else ""
        if cell_value in date_variants:
            return i + 1   # 1-based Excel row number
    return None


# ── Slack helpers ────────────────────────────────────────────────────────────

def get_reaction_count(channel: str, ts: str) -> int:
    """Return how many ✅ reactions the message has."""
    resp = requests.get(
        "https://slack.com/api/reactions.get",
        headers={"Authorization": f"Bearer {SLACK_USER_TOKEN}"},
        params={"channel": channel, "timestamp": ts, "full": True},
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"reactions.get error: {data.get('error')}")

    reactions = data.get("message", {}).get("reactions", [])
    for r in reactions:
        if r["name"] == "white_check_mark":
            return r["count"]
    return 0


def open_dm_channel(user_id: str) -> str:
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


def send_confirmation_dm(dm_channel: str, task_summary: str, date_str: str):
    text = (
        f"✅ *Tasks saved to timesheet!*\n"
        f"📅 Date: {date_str}\n\n"
        f"{task_summary}"
    )
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type":  "application/json",
        },
        json={"channel": dm_channel, "text": text, "mrkdwn": True},
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"chat.postMessage error: {data.get('error')}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== Reaction Check Script ===")

    # 1. Load state
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except FileNotFoundError:
        print("No state file found — daily_summary.py hasn't run yet today. Exiting.")
        return

    if state.get("saved"):
        print("Already saved to timesheet today. Exiting.")
        return

    channel      = state["channel"]
    ts           = state["ts"]
    task_summary = state["task_summary"]
    date_str     = state["date"]   # mm/dd/yy

    # 2. Check reaction count
    print(f"Checking ✅ reactions on message ts={ts}...")
    count = get_reaction_count(channel, ts)
    print(f"  Reaction count: {count}")

    if count < 2:
        print("  Not confirmed yet (need count >= 2). Exiting — will retry in 15 min.")
        return

    print("  Confirmed! Saving to timesheet...")

    # 3. Get MS Graph token
    print("Getting Microsoft Graph token...")
    token = get_ms_token()

    # 4. Read Excel to find today's row
    print(f"Reading Excel worksheet '{SHEET_NAME}'...")
    rows = get_worksheet_range(token, "A:C")

    row_num = find_row_for_today(rows, date_str)
    if row_num is None:
        print(f"  ⚠️  Could not find a row for date '{date_str}' in column A.")
        print("  Sending error DM...")
        dm_channel = open_dm_channel(MY_SLACK_USER_ID)
        send_confirmation_dm(
            dm_channel,
            f"⚠️ Could not find today's date ({date_str}) in the timesheet. Please update manually.\n\nTasks:\n{task_summary}",
            date_str,
        )
        return

    print(f"  Found today's row at Excel row {row_num}")
    cell_address = f"C{row_num}"

    # 5. Update column C with task summary
    update_cell(token, cell_address, task_summary)

    # 6. Send confirmation DM
    print("Sending confirmation DM...")
    dm_channel = open_dm_channel(MY_SLACK_USER_ID)
    send_confirmation_dm(dm_channel, task_summary, date_str)

    # 7. Mark state as saved
    state["saved"] = True
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    print("Done! Timesheet updated successfully. ✅")


if __name__ == "__main__":
    main()
