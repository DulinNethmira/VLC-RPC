import os
import json
import requests
import urllib.parse

# GitHub API Details
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    token = config.get("github_token")
except Exception:
    token = None

if not token:
    print("No GITHUB_TOKEN set. Release creation failed.")
    exit(1)

repo = "DulinNethmira/VLC-RPC"
tag = "v5.7.8"
title = "✨ v5.7.8 Hotfix - Networking & Discord Polish"
body = """### 🚀 What's Fixed in v5.7.8 Hotfix!
We've squashed a number of annoying bugs and leveled up the Local Media Library experience!

#### 🔧 Fixes & Tweaks
- **AniList DNS Hotfix**: Fixed an issue where temporary internet/DNS drops when resolving `graphql.anilist.co` would freeze background updates. The app now gracefully handles offline scenarios without locking up!
- **Library Group Modal**: Grouped Anime Series with apostrophes or special characters in their name (e.g. *Blood Blockade Battlefront's*) now successfully open the episode selection modal!
- **Discord RPC Stability**: Removed unsupported Discord IPC payload keys (like `activity_type`) and emojis in the `state` text which caused Discord to silently drop the RPC connection (`No response was received from the pipe in time`).

*(Note: The actual AniList background data server endpoint is exactly `https://graphql.anilist.co`, as documented officially at `https://docs.anilist.co`!)*

Enjoy the hotfix! 🎉"""

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

# Create Release
print("Creating GitHub release...")
url = f"https://api.github.com/repos/{repo}/releases"
data = {
    "tag_name": tag,
    "name": title,
    "body": body,
    "draft": False,
    "prerelease": False
}

r = requests.post(url, headers=headers, json=data)
if r.status_code == 201:
    res_data = r.json()
    upload_url = res_data['upload_url'].split('{')[0]
    print(f"Release created successfully! ID: {res_data['id']}")
    
    # Upload Asset
    asset_name = f"VLC RPC Setup {tag}.exe"
    asset_path = os.path.join("dist", asset_name)
    print(f"Uploading {asset_name} from {asset_path}...")
    
    if not os.path.exists(asset_path):
        print(f"ERROR: Could not find {asset_path}. Make sure Inno Setup has finished compiling!")
        exit(1)
        
    with open(asset_path, 'rb') as f:
        asset_data = f.read()
    
    upload_headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/octet-stream"
    }
    
    upload_target = f"{upload_url}?name={urllib.parse.quote(asset_name)}"
    ur = requests.post(upload_target, headers=upload_headers, data=asset_data)
    
    if ur.status_code == 201:
        print("Asset uploaded successfully! Release is live! 🎉")
    else:
        print(f"Asset upload failed: {ur.status_code} {ur.text[:300]}")
else:
    print(f"Release creation failed: {r.status_code} {r.text[:500]}")
