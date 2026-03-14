"""
get_sharepoint_ids.py
Run this ONCE locally to resolve your SharePoint share link into the
SITE_ID, DRIVE_ID, and ITEM_ID needed in your .env / GitHub Secrets.

Usage:
    python get_sharepoint_ids.py

It will prompt for your MS credentials and the share URL, then print
the three values you need to copy.
"""

import sys
import requests

def get_token(tenant_id, client_id, client_secret):
    url  = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://graph.microsoft.com/.default",
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def resolve_share_url(token, share_url):
    """
    Use the Graph 'shares' API to decode a SharePoint share URL
    and return (site_id, drive_id, item_id).
    """
    import base64
    # Encode the URL as required by Graph API
    encoded = base64.urlsafe_b64encode(share_url.encode()).decode().rstrip("=")
    share_token = f"u!{encoded}"

    # Resolve the shared item
    url  = f"https://graph.microsoft.com/v1.0/shares/{share_token}/driveItem"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"Error resolving share URL: {resp.status_code} {resp.text}")
        sys.exit(1)

    item    = resp.json()
    item_id = item["id"]

    # Get parent drive
    parent_ref  = item.get("parentReference", {})
    drive_id    = parent_ref.get("driveId", "")
    site_id_raw = parent_ref.get("siteId", "")

    return site_id_raw, drive_id, item_id


def main():
    print("=== SharePoint ID Resolver ===\n")
    tenant_id     = input("MS_TENANT_ID     : ").strip()
    client_id     = input("MS_CLIENT_ID     : ").strip()
    client_secret = input("MS_CLIENT_SECRET : ").strip()
    share_url     = input("SharePoint share URL : ").strip()

    print("\nFetching token...")
    token = get_token(tenant_id, client_id, client_secret)

    print("Resolving share URL...")
    site_id, drive_id, item_id = resolve_share_url(token, share_url)

    print("\n" + "="*50)
    print("✅ Copy these into your .env / GitHub Secrets:")
    print("="*50)
    print(f"SHAREPOINT_SITE_ID  = {site_id}")
    print(f"SHAREPOINT_DRIVE_ID = {drive_id}")
    print(f"SHAREPOINT_ITEM_ID  = {item_id}")
    print("="*50)


if __name__ == "__main__":
    main()
