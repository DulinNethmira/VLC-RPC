import urllib.request
import json
import os
import urllib.error

token = os.environ.get("GITHUB_TOKEN")
if not token:
    print("GITHUB_TOKEN not found.")
    exit(1)

url = "https://api.github.com/repos/DulinNethmira/VLC-RPC/releases"

title = "✨ v5.10.0 - Production Metadata Engine"
body = """### 🚀 What's New in v5.10.0!
We've completely overhauled how VLC RPC handles media metadata to make it faster, safer, and much more accurate.

#### 🧠 Production Metadata Engine
- **Centralized Pipeline**: All metadata parsing is now handled by a dedicated engine.
- **Dual-Key Caching**: Renaming or moving your files no longer breaks your cached metadata! The engine can recognize the file by name alone and fetch your existing cache instantly.
- **Negative Caching**: The app will no longer spam APIs for unrecognized files, drastically reducing network overhead.
- **Deduplicated Background Resolution**: Skipping rapidly through a season will no longer launch dozens of identical requests. The engine handles request piggybacking seamlessly.

#### 🔧 Fixes & Tweaks
- Fully eliminated race conditions where older requests could overwrite newer ones if you swapped episodes too quickly.
- Built-in strict crash resilience using atomic file writes to ensure your `metadata_cache.json` never gets corrupted during a power loss.
- Legacy `metadata_cache.json` files are automatically upgraded to the new rich format on load.

Enjoy the new update! 🎉"""

data = {
    "tag_name": "v5.10.0",
    "target_commitish": "main",
    "name": title,
    "body": body,
    "draft": False,
    "prerelease": False,
    "generate_release_notes": False
}

req = urllib.request.Request(url, method="POST")
req.add_header("Authorization", f"Bearer {token}")
req.add_header("Accept", "application/vnd.github.v3+json")
req.add_header("Content-Type", "application/json")

encoded_data = json.dumps(data).encode('utf-8')

try:
    with urllib.request.urlopen(req, data=encoded_data) as response:
        print(f"Release created successfully! Status code: {response.getcode()}")
        resp_data = json.loads(response.read().decode('utf-8'))
        print(f"Release URL: {resp_data.get('html_url')}")
except Exception as e:
    print(f"Failed to create release: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
