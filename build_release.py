import os
import sys
import subprocess
import glob
import urllib.request
import urllib.parse
import json

def get_or_create_release(repo, tag_name, token, name=None, body=None):
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Create release
            create_url = f"https://api.github.com/repos/{repo}/releases"
            data = {
                "tag_name": tag_name,
                "name": name or f"🚀 VLC RPC {tag_name}",
                "body": body or f"## What's New in {tag_name}!\n\nThis release includes major updates to the notification and update system.",
                "draft": False,
                "prerelease": False
            }
            req = urllib.request.Request(
                create_url, 
                data=json.dumps(data).encode('utf-8'), 
                headers=headers, 
                method="POST"
            )
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        else:
            raise

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)

    print("Building application with PyInstaller...")
    subprocess.run([r".\venv\Scripts\pyinstaller.exe", "-y", "VLC RPC.spec"], check=True)

    print("Compiling installer with Inno Setup...")
    iscc_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")
    if not os.path.exists(iscc_path):
        print(f"Error: Inno Setup compiler not found at {iscc_path}")
        sys.exit(1)
    
    subprocess.run([iscc_path, "setup.iss"], check=True)

    print("Uploading to GitHub...")
    repo = "DulinNethmira/VLC-RPC"
    tag_name = "v6.1.0"
    release_title = "\u2728 v6.1.0 - Massive Dashboard Redesign!"
    release_notes = """### \U0001f680 What's New in v6.1.0!

We've completely overhauled the VLC RPC Dashboard to give you a true command center experience. 

#### 🎨 Brand New Dashboard Layout
- **Hero Display**: Now features the active Anime Sync Status directly on the cover art.
- **Summary Cards**: Quick stats for Today's watch time, AniList Sync Queue, and System Health.
- **Airing Soon**: Never miss an episode! The dashboard now fetches and caches the next airing times for the anime you're currently watching.
- **Smart Activity Feed**: We filtered out the technical noise so you only see what matters (started watching, finished episode, synced).

#### 🔍 Quality of Life
- **Dashboard Scale**: Added a new zoom slider in Settings (70% - 130%) so you can size the dashboard perfectly without affecting other tabs.
- **Action Required Banner**: Instantly know when something goes wrong with AniList syncs or system health.

Enjoy the new look! 🎉
"""

    try:
        release = get_or_create_release(repo, tag_name, token, name=release_title, body=release_notes)
        
        # Inno Setup output is usually VLC RPC Setup.exe in dist folder
        file_path = f"dist\\VLC RPC Setup {tag_name}.exe"
        if not os.path.exists(file_path):
            print(f"No setup executable found at {file_path}")
            sys.exit(1)
            
        # Delete old assets to avoid 422
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        for asset in release.get("assets", []):
            if asset['name'] == f"VLC RPC Setup {tag_name}.exe":
                print(f"Deleting existing asset: {asset['name']}")
                req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                urllib.request.urlopen(req)
                
        # Upload
        upload_url = release["upload_url"].split("{")[0]
        filename = f"VLC RPC Setup {tag_name}.exe"
        url = f"{upload_url}?name={urllib.parse.quote(filename)}"
        
        with open(file_path, 'rb') as f:
            file_data = f.read()

        req = urllib.request.Request(
            url,
            data=file_data,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/octet-stream"
            },
            method="POST"
        )
        print(f"Uploading {filename} to {url}...")
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                print("Asset uploaded successfully!")
            else:
                print(f"Failed to upload asset. Status: {response.status}")
                
        print(f"All done! Release URL: {release.get('html_url')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
