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
    
    tag_name = "v5.4.0"
    
    release_title = "✨ v5.4.0 - Major Forensic Metadata Repair & AniList Identity Upgrade"
    release_notes = """### 🚀 What's New in v5.4.0!

We're proud to present **v5.4.0**, a major release bringing full forensic repairs to title recognition, AniList identity scoring, metadata caching, and frontend cover art rendering!

#### 🌸 AniList Identity & Season Matching Upgrade
- **Season-Aware Matching:** Fixed scoring so titles like *Tokyo Ghoul:re (Season 3)* match their exact AniList identity (ID 100240) instead of being incorrectly penalized or rejected.
- **Sequel Preservation:** Distinguishes numeric sequels (*Overlord II*) from base titles (*Overlord*), ensuring zero identity mix-ups.
- **Authoritative AniList Identity:** SYNCABLE AniList identities now serve as the primary, authoritative metadata source without redundant title searches.

#### ⚡ Metadata Cache & Hardening
- **Stale Worker Ordering:** Cache mutations are now generation-guarded, preventing stale worker threads from polluting the persistent metadata cache.
- **Collision-Resistant Keys:** Preserved semantic title words (`the`, `a`, `an`) to guarantee unique cache keying.
- **Force Sync Repair:** Refactored `Force Sync` to use the unified cache key generator, invalidating negative cache markers while preserving identity and rewatch states.

#### 🤖 Gemini AI & Deterministic Fallback
- **Header Auth & Validation:** Upgraded Gemini API queries to use `x-goog-api-key` headers and strict schema validation.
- **Pending Recovery:** Added automatic timeout and recovery to prevent filenames from remaining stuck in a pending state.
- **Enhanced Deterministic Parser:** Improved `clean_title` to handle fansub group tags (`[SubsPlease]`), `SxxExx` notation, subtitle colons, and Roman numerals.

#### 🎨 Frontend UI & Cover Art Fallback
- **Strict Resolution Hierarchy:** Streamlined cover art fallback (`scene_snapshot` -> `metadata.image_url` -> `local_arturl` -> `placeholder`) so valid covers never get stuck on placeholders.
- **Official Title Display:** Dashboard automatically displays official database titles when resolved.

#### 🧪 Comprehensive Regression Testing
- **100% Test Suite Coverage:** Added 12 new regression test cases (A–L) covering all edge cases.

Enjoy the ultimate VLC RPC experience! 🎉"""

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
