import sys

with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "f\"Bearer {access, 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'}\"",
    "f\"Bearer {access}\", 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'"
)
content = content.replace(
    "f\"Bearer {token, 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'}\"",
    "f\"Bearer {token}\", 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'"
)
content = content.replace(
    "f'Bearer {token, \\'User-Agent\\': \\'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)\\'}'",
    "f'Bearer {token}', 'User-Agent': 'VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)'"
)

with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)
