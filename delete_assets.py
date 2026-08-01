import os
import sys
import json
import urllib.request
import urllib.error

def main():
    token = os.environ.get("GITHUB_TOKEN")
    repo = "DulinNethmira/VLC-RPC"
    tag_name = "v4.8.0"

    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get release
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        release = json.loads(response.read().decode('utf-8'))
    
    # Delete all assets
    for asset in release.get("assets", []):
        asset_url = asset["url"]
        print(f"Deleting asset: {asset['name']}")
        req = urllib.request.Request(asset_url, headers=headers, method="DELETE")
        urllib.request.urlopen(req)

if __name__ == "__main__":
    main()
