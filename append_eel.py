import os

append_code = """
backend = RPCBackend()

@eel.expose
def get_config():
    return backend.config

@eel.expose
def save_config(new_config):
    try:
        backend.config.update(new_config)
        save_config_func(backend.config)  # using the global one
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@eel.expose
def force_update():
    eel.updateState(backend.state_data)()

def update_ui_loop():
    while not backend.state_data["exit_flag"]:
        eel.updateState(backend.state_data)()
        eel.sleep(1)

def setup_tray():
    def on_quit(icon, item):
        backend.state_data["exit_flag"] = True
        icon.stop()
        os._exit(0)
        
    def on_show(icon, item):
        # We cannot easily unminimize Eel window cross-platform from a background thread
        pass
        
    image_path = "web/icon.ico"
    if os.path.exists(image_path):
        image = Image.open(image_path)
    else:
        image = Image.new('RGB', (64, 64), color='black')
        
    menu = pystray.Menu(pystray.MenuItem('Quit', on_quit))
    icon = pystray.Icon("vlc_rpc", image, "VLC Discord RP", menu)
    icon.run()

if __name__ == '__main__':
    # Need to alias the global save_config to avoid shadowing in Eel
    global save_config_func
    save_config_func = save_config

    threading.Thread(target=setup_tray, daemon=True).start()
    
    eel.init('web')
    eel.spawn(update_ui_loop)
    
    try:
        eel.start('index.html', size=(680, 640), port=0)
    except (SystemExit, KeyboardInterrupt):
        pass
        
    backend.state_data["exit_flag"] = True
    os._exit(0)
"""

with open('main.py', 'a', encoding='utf-8') as f:
    f.write(append_code)
