import urllib.request
import json
import os
import ssl

try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    token = config.get("github_token")
except Exception:
    token = None

if not token:
    print("No GITHUB_TOKEN set. Release creation failed.")
    exit(1)

url = "https://api.github.com/repos/DulinNethmira/VLC-RPC/releases"

body = """### 🚀 What's New in v5.8.0!
We've completely overhauled the notification system to ensure VLC RPC never interrupts your watch experience again!

#### 🔔 Smart Notifications
- **Intelligent Suppression**: Normal notifications (Media Detected, Episode Changed, AniSkip info) are silently suppressed if you are actively watching.
- **Aggressive Deduplication & Cooldowns**: Eliminates notification spam without missing important events.
- **Smart Queuing & Flushing**: When you stop playback, the system evaluates all suppressed notifications and intelligently merges repeated events (e.g., "AniSkip (+2 merged)").
- **Critical Override**: True failures and critical errors ignore standard playback suppression so you know immediately if something requires intervention (like an expired AniList token).

#### 🖥️ UI Enhancements
- **New Notification Settings**: A new "Smart Notifications" section in the Settings tab allows you to configure your preferred verbosity (Enabled, Critical Only, Disabled) and toggle the "Suppress while playing" feature.
- **Notification History Viewer**: Click "View Notification History" to open a sleek modal that shows exactly what notifications were Displayed 🟢, Suppressed 🔴, or Deferred 🟡!

Enjoy the uninterrupted watch experience! 🎉
"""

payload = {
    "tag_name": "v5.8.0",
    "target_commitish": "main",
    "name": "✨ v5.8.0 - Centralized Smart Notifications",
    "body": body,
    "draft": False,
    "prerelease": False,
    "generate_release_notes": False
}

req = urllib.request.Request(url, method="POST")
req.add_header("Authorization", f"Bearer {token}")
req.add_header("Accept", "application/vnd.github.v3+json")
req.add_header("X-GitHub-Api-Version", "2022-11-28")

data = json.dumps(payload).encode("utf-8")

# Ignore SSL verification if needed, but normally fine
ctx = ssl.create_default_context()
try:
    with urllib.request.urlopen(req, data=data, context=ctx) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print("Error:", e.status, e.read().decode("utf-8"))
