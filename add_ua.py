import os
import re

def add_ua(filepath):
    if not os.path.exists(filepath):
        print(f'Skipped {filepath}')
        return
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern 1: headers = {'Authorization': ...}
    # Add User-Agent to single line dictionary definitions that don't have it
    content = re.sub(
        r'(headers\s*=\s*\{([^}]*?))(?=\})',
        lambda m: m.group(1) + (", 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'" if 'User-Agent' not in m.group(1) else ""),
        content
    )

    # Pattern 2: line 6115 requests.post(...)
    content = content.replace(
        'response = requests.post("https://graphql.anilist.co", json={"query": query, "variables": {"search": title}}, timeout=5)',
        'response = requests.post("https://graphql.anilist.co", json={"query": query, "variables": {"search": title}}, headers={"Content-Type": "application/json", "User-Agent": "VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)"}, timeout=5)'
    )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Updated {filepath}')

add_ua('vlc_discord_rpc_gui.py')
add_ua('notifier_worker.py')
add_ua('insert_diagnostics.py')
