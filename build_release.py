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
    tag_name = "v4.9.9"
    
    release_title = "✨ v4.9.8 - Massive Feature Update: Analytics & Themes!"
    release_notes = """### 🚀 What's New in v4.9.8!

#### 📊 Advanced Analytics
- **New Stats**: Added Average Session Length and Most Binge-Watched Day!
- **UI Enhancements**: Weekly Activity chart now properly displays in Hours instead of Minutes, and we fixed the 119 Hours bug!
- **Share Anime Wrap**: Generate and download a beautiful image of your Anime Wrap directly from the Analytics tab to share with your friends!

#### 🎨 Custom Accent Themes
- **Personalize Your App**: Added a new Theme selector in the Preferences tab! Choose from Discord Blurple, Ruby Red, Emerald Green, Neon Purple, Sunset Orange, Hot Pink, or Cyan Blue.

#### ⚙️ Quality of Life Fixes
- **Discord RPC Toggle**: You can now instantly toggle your Discord Activity ON/OFF directly from the Dashboard using the new `RPC Active` button!
- **Sidebar Version**: Added a sleek version tracker to the sidebar so you always know what version you're on.
- **Log Improvements**: Fixed an issue where Gemini AI would spam "Failed to resolve title" logs. It now auto-retries elegantly in the background once every hour!
"""

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
