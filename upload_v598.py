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

tag_name = "v5.9.8"
repo = "DulinNethmira/VLC-RPC"
url = f"https://api.github.com/repos/{repo}/releases"
name = f"✨ v5.9.8 - Dismiss Continue Watching! ❌"
body = """### 🚀 What's New in v5.9.8!

A highly requested quality-of-life feature to keep your Continue Watching rail clean!

#### ❌ Dismiss Continue Watching
- **Mark as Finished**: Anime you finished watching but are permanently stuck in the "Continue Watching" rail (due to skipping the OP/ED or watching at 2x speed) can now be manually dismissed!
- **Sleek UI**: Just hover over any card in the Continue Watching rail and click the subtle 'X' button to instantly clear it from your active watchlist. It will no longer haunt you!

Enjoy the clean slate! 🎉"""

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
