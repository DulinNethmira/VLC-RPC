import re

for filepath in ['vlc_discord_rpc_gui.py', 'notifier_worker.py', 'insert_diagnostics.py']:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # The faulty pattern: {'Authorization': f'Bearer {token, 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'}'
        # or {'Authorization': 'Bearer ' + self.backend_ref.config.get("anilist_token"), 'User-Agent': ...}
        
        # Let's fix line 2491 and 2290 specifically.
        content = content.replace(
            "f'Bearer {token, 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'}'",
            "f'Bearer {token}', 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'"
        )
        content = content.replace(
            "config.get(\"anilist_token\"), 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'}",
            "config.get(\"anilist_token\")}, 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'" # wait this might not be it. Let's just use regex to fix any malformed braces if needed, or simply print the lines with User-Agent to see what they look like.
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
