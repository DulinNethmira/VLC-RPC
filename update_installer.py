import os
import sys
import shutil
import ctypes
import subprocess
import time

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def log(msg):
    try:
        with open("C:\\updater_log.txt", "a") as f:
            f.write(f"[{time.ctime()}] {msg}\n")
    except:
        pass
    print(msg)

def main():
    log("Started VLC RPC Update Installer")
    if not is_admin():
        log("Requesting admin privileges...")
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv[1:]), None, 1)
        sys.exit()

    log("Running as Admin. Proceeding with update...")
    target_dir = os.environ.get('PROGRAMFILES', 'C:\\Program Files') + "\\VLC RPC"
    
    # Force kill VLC RPC and all its child processes (pywebview spawns many)
    log("Killing existing VLC RPC.exe processes...")
    subprocess.call(["taskkill", "/F", "/T", "/IM", "VLC RPC.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.call(["taskkill", "/F", "/T", "/IM", "vlc_discord_rpc_gui.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3) # Give Windows time to release file handles
    
    # Try multiple times just in case
    for _ in range(3):
        subprocess.call(["taskkill", "/F", "/T", "/IM", "VLC RPC.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    # Copy files
    if getattr(sys, 'frozen', False):
        bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        source_dir = os.path.join(bundle_dir, "app_data")
        
        if os.path.exists(source_dir):
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            log(f"Copying files from {source_dir} to {target_dir}")
            try:
                for item in os.listdir(source_dir):
                    s = os.path.join(source_dir, item)
                    d = os.path.join(target_dir, item)
                    
                    # Try to remove destination if it exists
                    if os.path.exists(d):
                        try:
                            if os.path.isdir(d):
                                shutil.rmtree(d)
                            else:
                                os.remove(d)
                        except Exception as e:
                            log(f"Failed to remove {d}: {e}")
                            # If it's a locked file, try renaming it to a temp file so we can copy the new one over
                            try:
                                temp_name = d + f".old_{int(time.time())}"
                                os.rename(d, temp_name)
                                log(f"Renamed locked file {d} to {temp_name}")
                            except Exception as re:
                                log(f"Failed to rename {d}: {re}")

                    if os.path.isdir(s):
                        if not os.path.exists(d):
                            shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
                log("Update completed successfully!")
            except Exception as e:
                log(f"Error during copy: {e}")
        else:
            log(f"Source dir {source_dir} not found!")
    else:
        log("Not running frozen, skipping copy.")
    
    # Relaunch
    exe_path = os.path.join(target_dir, "VLC RPC.exe")
    if os.path.exists(exe_path):
        log(f"Relaunching {exe_path}")
        subprocess.Popen([exe_path], creationflags=subprocess.DETACHED_PROCESS)
    else:
        log(f"Executable not found at {exe_path} after update!")

if __name__ == "__main__":
    main()
