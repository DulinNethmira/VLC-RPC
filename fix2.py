import re

def fix_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i in range(len(lines)):
            if "}, 'User-Agent':" in lines[i]:
                lines[i] = lines[i].replace("}, 'User-Agent':", ", 'User-Agent':") + "}"
                # The line now might end with `(Windows NT 10.0; Win64; x64)'\n}` so let's clean it up
                lines[i] = lines[i].replace("'\n}", "'}\n").replace("'\r\n}", "'}\r\n")
            
            # also fix if it was f'Bearer {token}'}, 'User-Agent'
            if "'}, 'User-Agent':" in lines[i]:
                lines[i] = lines[i].replace("'}, 'User-Agent':", "', 'User-Agent':") + "}"
                lines[i] = lines[i].replace("'\n}", "'}\n").replace("'\r\n}", "'}\r\n")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

fix_file('vlc_discord_rpc_gui.py')
fix_file('notifier_worker.py')
fix_file('insert_diagnostics.py')
