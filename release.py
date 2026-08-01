import os
import sys
import json
import urllib.request
import urllib.error

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)

    repo = "DulinNethmira/VLC-RPC"
    tag_name = "v4.8.0"
    title = "✨ v4.8.0 - Massive Feature Update: Analytics & AniSkip"
    body = """### 🚀 What's New in v4.8.0!
We've added a ton of highly requested features to make your anime tracking experience even better.

#### 📊 Your Anime Wrap (Analytics)
- **New Dashboard Tab**: View your total hours watched, unique titles, and today's stats.
- **Activity Graph**: A beautiful 7-day bar chart of your watch history.
- **Top Titles**: See which anime you've spent the most time on!

#### ⏭️ AniSkip Integration
- **Auto-Skip**: Automatically jump over Openings (OP) and Endings (ED).
- **Smart Detection**: Only skips if you're watching the correct episode based on AniList data.

#### ⭐ Auto-Score Popups
- Automatically prompts you to rate a series the moment you finish the final episode.
- **Custom Rating Formats**: Automatically matches your AniList preference (100-point, 10-point, 5-star, or smiley faces).

#### 🍎 UI Enhancements
- **macOS-Style Toasts**: Replaced standard logs with sleek, animated dark-mode toast notifications for syncs and skips!

### 🔧 Fixes & Tweaks
- Added new preferences toggles for Auto-Skip and Auto-Score.
- System Tray integration improvements.

Enjoy the new update! 🎉
"""

    payload = {
        "tag_name": tag_name,
        "name": title,
        "body": body,
        "draft": False,
        "prerelease": False
    }

    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases",
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json; charset=utf-8"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                res_body = json.loads(response.read().decode('utf-8'))
                print(f"✅ Release created successfully! URL: {res_body.get('html_url')}")
            else:
                print(f"❌ Failed to create release. Status: {response.status}")
                print(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        print(e.read().decode('utf-8'))
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
