import urllib.request
import json
import os
import subprocess
import urllib.parse
import sys

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

# 1. Fetch the latest release to get upload_url
print("Fetching release info...")
req = urllib.request.Request("https://api.github.com/repos/DulinNethmira/VLC-RPC/releases/tags/v5.8.0", headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        upload_url = res_data['upload_url'].split('{')[0]
except Exception as e:
    print("Failed to fetch release:", e)
    sys.exit(1)

# 2. Compile .exe
print("Building application with PyInstaller...")
subprocess.run([r".\venv\Scripts\pyinstaller.exe", "-y", "VLC RPC.spec"], check=True)

print("Compiling installer with Inno Setup...")
iscc_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")
subprocess.run([iscc_path, "setup.iss"], check=True)

# 3. Upload Asset
tag = "v5.8.0"
asset_name = f"VLC RPC Setup {tag}.exe"
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
    with urllib.request.urlopen(req) as response:
        if response.status == 201:
            print("Asset uploaded successfully! Release is live! 🎉")
        else:
            print(f"Asset upload failed: {response.status}")
except Exception as e:
    print(f"Asset upload error: {e}")
