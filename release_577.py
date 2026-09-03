import os
import json
import requests
import zipfile

def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), 
                       os.path.relpath(os.path.join(root, file), 
                                       os.path.join(path, '..')))

# Create zip file
print("Creating zip file...")
zipf = zipfile.ZipFile('VLC-RPC-v5.7.7.zip', 'w', zipfile.ZIP_DEFLATED)
zipdir('dist/vlc_discord_rpc_gui', zipf)
zipf.close()
print("Zip created successfully!")

# GitHub API Details
token = os.environ.get('GITHUB_TOKEN')
if not token:
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        token = config.get("github_token")
    except Exception:
        pass

if not token:
    print("No GITHUB_TOKEN set. Release creation failed.")
    exit(1)

repo = "DulinNethmira/VLC-RPC"
tag = "v5.7.7"
title = "✨ v5.7.7 - Local Library Polish & Bug Fixes"
body = """### 🚀 What's New in v5.7.7!
We've squashed a number of annoying bugs and leveled up the Local Media Library experience!

#### 🍎 UI Enhancements
- **Sleek Grouping**: Grouped Anime Series now open a beautiful episode selection modal instead of immediately playing the first file.
- **Force Clear**: Added a new "Force Clear" button on the dashboard to easily wipe a ghosted VLC state.
- **Streaming Aesthetics**: The library cards now look and feel just like your favorite anime streaming sites!

#### 🔧 Fixes & Tweaks
- **Auto-Scanner Revamped**: The background scanner now aggressively forces AniList cover fetches even if the file hasn't changed, populating missing images instantly.
- **Fallback Playback**: Clicking play on a library file while VLC is closed no longer displays an error; it seamlessly auto-launches the file via your OS defaults!
- **URL Path Decoding**: Fixed a bug where playing files directly from the library would cause metadata scraping to fail due to VLC URL encoding.
- **Smart Dashboard Updates**: The UI now handles VLC pauses and background ghosting much more gracefully.
- Removed a stubborn duplicate version tag that was breaking the built-in updater.

Enjoy the polish! 🎉"""

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
    asset_name = "VLC-RPC-v5.7.7.zip"
    print(f"Uploading {asset_name}...")
    with open(asset_name, 'rb') as f:
        asset_data = f.read()
    
    upload_headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/zip"
    }
    
    ur = requests.post(f"{upload_url}?name={asset_name}", headers=upload_headers, data=asset_data)
    if ur.status_code == 201:
        print("Asset uploaded successfully! Release is live! 🎉")
    else:
        print(f"Asset upload failed: {ur.status_code} {ur.text[:300]}")
else:
    print(f"Release creation failed: {r.status_code} {r.text[:500]}")
