import urllib.request
import json
import os
import subprocess
import urllib.parse
import sys
import ssl

try:
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    token = config.get("github_token")
except Exception:
    token = None

if not token:
    print("No GITHUB_TOKEN set. Release creation failed.")
    sys.exit(1)

headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}
ctx = ssl.create_default_context()

tag_name = "v5.9.4"
repo = "DulinNethmira/VLC-RPC"
url = f"https://api.github.com/repos/{repo}/releases"
name = f"✨ v5.9.4 - The Artwork Engine Update 🎨"
body = """### 🚀 What's New in v5.9.4!

We've completely rebuilt the core artwork retrieval system to be faster, more robust, and entirely non-blocking!

#### 🎨 Centralized Artwork Engine
- **Non-blocking UI**: Massive image strings are no longer passed around, resulting in a buttery smooth UI and fewer freezes.
- **Offline Mode**: Images are now intelligently cached on your machine. No more waiting for images to load when repeating episodes!
- **Imgur Smart-Sync**: Embedded local artwork is now only uploaded to Imgur when Discord RPC explicitly requests it, keeping API calls minimal and rate-limits happy.
- **Concurrent Deduplication**: Quickly skipping through tracks no longer spawns duplicate network requests!

#### 🔧 Fixes & Tweaks
- **Diagnostics Integration**: Diagnostics Center now tracks Cache Hits, Misses, and Active Providers for your artwork.
- **Bounded Cache Limits**: Ensures the artwork cache never fills up your hard drive (max 200 items automatically purged via LRU).

Enjoy the new update! 🎉"""

payload = {
    "tag_name": tag_name,
    "target_commitish": "main",
    "name": name,
    "body": body,
    "draft": False,
    "prerelease": False
}

print("Creating release...")
req = urllib.request.Request(url, method="POST", data=json.dumps(payload).encode("utf-8"), headers=headers)
try:
    with urllib.request.urlopen(req, context=ctx) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        upload_url = res_data['upload_url'].split('{')[0]
except Exception as e:
    print("Failed to create release:", e)
    sys.exit(1)

# Compile .exe
print("Building application with PyInstaller...")
subprocess.run([r".\venv\Scripts\pyinstaller.exe", "-y", "VLC RPC.spec"], check=True)

print("Compiling installer with Inno Setup...")
iscc_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")
subprocess.run([iscc_path, "setup.iss"], check=True)

# Upload Asset
asset_name = f"VLC RPC Setup {tag_name}.exe"
asset_path = os.path.join("dist", asset_name)

print(f"Uploading {asset_name} from {asset_path}...")
if not os.path.exists(asset_path):
    print(f"ERROR: Could not find {asset_path}.")
    sys.exit(1)

with open(asset_path, 'rb') as f:
    asset_data = f.read()

upload_headers = {
    "Authorization": f"token {token}",
    "Content-Type": "application/octet-stream",
    "Accept": "application/vnd.github.v3+json"
}

upload_target = f"{upload_url}?name={urllib.parse.quote(asset_name)}"
req = urllib.request.Request(upload_target, data=asset_data, headers=upload_headers, method="POST")
try:
    with urllib.request.urlopen(req, context=ctx) as response:
        if response.status == 201:
            print("Asset uploaded successfully! Release is live!")
        else:
            print(f"Asset upload failed: {response.status}")
except Exception as e:
    print(f"Asset upload error: {e}")
