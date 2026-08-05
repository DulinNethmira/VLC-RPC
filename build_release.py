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
    tag_name = "v5.0.0"
    
    release_title = "🚀 v5.0.0 - The V5 Milestone: Fully Stable & Polished"
    release_notes = """### 🔥 What's New in v5.0.0!

This is a **major milestone release**. VLC RPC is now fully stable, polished, and packed with features. Welcome to Version 5!

#### 🎨 Custom Accent Themes
- **7 Unique Themes**: Choose from Discord Blurple, Ruby Red, Emerald Green, Neon Purple, Sunset Orange, Hot Pink, or Cyan Blue in the Preferences tab!

#### 📊 Anime Wrapped & Advanced Analytics
- **Anime Wrap Card**: Generate and download a beautiful shareable image of your anime stats directly from the Analytics tab!
- **Deep Stats**: Total hours watched, Average Session Length, Most Binge-Watched Day, and a 7-day Activity Graph!

#### 📡 Discord Presence Overhaul
- **RPC Toggle**: Instantly pause/resume your Discord Activity from the Dashboard with one click.
- **Genre + Rating Display**: Your presence now shows clean genre tags and star ratings from AniList/IMDb.
- **Fixed Emoji Corruption**: All special characters (⭐, →, —, •, ❌, ✅) in the presence text are now rendered perfectly.

#### ⚡ Startup & Stability Fixes
- **Startup Freeze Eliminated**: Fixed a deep PyWebView recursion crash that caused the app to hang on "Connecting to engines..." indefinitely.
- **Encoding Fixed**: Resolved all double-encoded UTF-8 corruption that appeared as garbage characters (â€", â†', âŒ) throughout the app logic.
- **Gemini Log Spam Fixed**: Eliminated the "Failed to resolve title" log spam — Gemini now auto-retries silently once per hour.

#### 🌐 UI & QoL
- **Sidebar Version**: Always know what version you're running from the sidebar.
- **macOS-Style Toasts**: Sleek animated dark-mode notifications for app events.
- **Auto-Score Popups**: Automatically prompts you to rate an anime when you finish the final episode.
- **AniSkip Integration**: Auto-skip Openings and Endings based on your AniList episode data.

Enjoy v5! 🎉"""

    try:
        release = get_or_create_release(repo, tag_name, token, name=release_title, body=release_notes)
        
        # Inno Setup output is usually VLC RPC Setup.exe in dist folder
        file_path = r"dist\VLC RPC Setup.exe"
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
