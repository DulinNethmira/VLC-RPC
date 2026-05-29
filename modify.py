import re

with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace imports
code = code.replace('import tkinter as tk\nimport customtkinter as ctk\n', 'import eel\nimport pystray\n')

# Replace class definition
code = code.replace('class VLCRPCApp(ctk.CTk):', 'class RPCBackend:')

# Remove create_widgets and its callers
code = re.sub(r'        super\(\)\.__init__\(\)\n        \n', '', code)
code = re.sub(r'        # Window setup.*?self\.configure\(fg_color="#0c0214"\)\n        \n', '', code, flags=re.DOTALL)
code = re.sub(r'        # Setup UI\n        self\.create_widgets\(\)\n        \n', '', code)
code = re.sub(r'        # Start GUI update loop\n        self\.update_gui_loop\(\)\n        \n', '', code)
code = re.sub(r'        self\.protocol\("WM_DELETE_WINDOW", self\.on_closing\)\n', '', code)

# Remove the entire create_widgets block and update_gui_loop
code = re.sub(r'    def create_widgets\(self\):.*?    def on_closing\(self\):', '    def on_closing(self):', code, flags=re.DOTALL)

# Remove the "if __name__ == '__main__':" block at the end
code = re.sub(r'if __name__ == "__main__":.*?$', '', code, flags=re.DOTALL)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(code)
