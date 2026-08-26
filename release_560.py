import os
import sys
import subprocess
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
            create_url = f"https://api.github.com/repos/{repo}/releases"
            data = {
                "tag_name": tag_name,
                "name": name or f"✨ VLC RPC {tag_name}",
                "body": body or f"## Release {tag_name}",
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
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        token = config.get("github_token") or os.environ.get("GITHUB_TOKEN")
    except Exception:
        token = os.environ.get("GITHUB_TOKEN")
        
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)

    print("1. Building application executable with PyInstaller...")
    subprocess.run([r".\venv\Scripts\pyinstaller.exe", "-y", "VLC RPC.spec"], check=True)

    print("2. Compiling installer with Inno Setup...")
    iscc_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")
    if not os.path.exists(iscc_path):
        iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not os.path.exists(iscc_path):
        print(f"Error: Inno Setup compiler not found.")
        sys.exit(1)
    
    subprocess.run([iscc_path, "setup.iss"], check=True)

    print("3. Creating GitHub release and uploading installer...")
    repo = "DulinNethmira/VLC-RPC"
    
    tag_name = "v5.6.0"
    
    release_title = "🌸 v5.6.0 - Full Anime Detection & AniList Rewatch Restoration"
    release_notes = """### 🚀 What's New in v5.6.0!

We're proud to bring you **v5.6.0**, restoring full Anime detection, official AniList metadata covers, and automatic Rewatch status detection!

#### 🌸 Default Anime Routing & Media Type Repair
- **Default Anime Classification:** Video files without explicit `"anime"` strings in their file path are now defaulted to `anime` media type instead of `movie` or `tv_show`.
- **Prevented Misclassification:** Removed automatic override of anime files to `tv_show` when episode strings are present, unlocking AniList identity resolution for all anime files.
- **Official Cover Art:** Restored automatic cover art fetching from AniList for titles like *Tokyo Ghoul;re*.

#### 🔄 AniList Rewatch Detection & Syncing
- **Automatic Rewatch Identification:** Triggers AniList list status queries for series like *Tokyo Ghoul;re*, correctly activating `REWATCHING` watch modes and Discord RPC presence.
- **TVMaze & OMDb Fallbacks:** Added seamless secondary fallbacks so non-anime video files still resolve clean cover art and metadata.

#### 🧪 Expanded Regression Coverage
- Verified with new regression test `test_regression_o_tokyo_ghoul_re_default_anime_media_type`.

Enjoy your anime rewatching experience! 🎉"""

    try:
        release = get_or_create_release(repo, tag_name, token, name=release_title, body=release_notes)
        
        file_path = rf"dist\VLC RPC Setup {tag_name}.exe"
        if not os.path.exists(file_path):
            print(f"No setup executable found at {file_path}")
            sys.exit(1)
            
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        for asset in release.get("assets", []):
            if asset['name'] == f"VLC RPC Setup {tag_name}.exe":
                print(f"Deleting existing asset: {asset['name']}")
                req = urllib.request.Request(asset["url"], headers=headers, method="DELETE")
                urllib.request.urlopen(req)
                
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
        print(f"Uploading {filename} to GitHub release...")
        with urllib.request.urlopen(req) as response:
            if response.status in (200, 201):
                print("Asset uploaded successfully!")
            else:
                print(f"Failed to upload asset. Status: {response.status}")
                
        print(f"\n🎉 Release {tag_name} successfully published! Release URL: {release.get('html_url')}")
    except Exception as e:
        print(f"Error publishing release: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
