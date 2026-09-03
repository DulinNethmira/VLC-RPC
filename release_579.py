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
tag = "v5.7.9"
title = "✨ v5.7.9 Hotfix - Discord Formatting Polish"
body = """### 🚀 What's Fixed in v5.7.9 Hotfix!
We heard your feedback about the Discord Activity formatting! We've immediately reverted the activity card back to exactly the way you liked it.

#### 🔧 Fixes & Tweaks
- **Activity Status Restored**: "Playing VLC Media Player" has been successfully restored back to "Watching" (for anime/movies) and "Listening" (for music)!
- **Emoji Restoration**: The ⭐ icon for scores and the 🔄 icon for rewatching have been restored.
- Retained the DNS resilience and UI fixes from 5.7.8 under the hood.

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
