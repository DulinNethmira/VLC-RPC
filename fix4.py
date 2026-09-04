import re

with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix f-string syntax errors from earlier
content = re.sub(
    r"f'Bearer \{([^,}]+),\s*'User-Agent':\s*'VLC-RPC/6\.1\.8[^']+'\}'",
    r"f'Bearer {\1}', 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'",
    content
)

content = re.sub(
    r"f\"Bearer \{([^,}]+),\s*'User-Agent':\s*'VLC-RPC/6\.1\.8[^']+'\}\"",
    r"f\"Bearer {\1}\", 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'",
    content
)

with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)
