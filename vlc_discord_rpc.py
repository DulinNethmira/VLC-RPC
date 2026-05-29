import os
import sys
import time
import json
import requests
from pypresence import Presence
from pypresence.exceptions import DiscordNotFound, DiscordError
from requests.auth import HTTPBasicAuth
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.progress import ProgressBar
from rich.table import Table
from rich.align import Align
from rich.text import Text

# Initialize Rich Console
console = Console()

CONFIG_FILE = "config.json"
DEFAULT_CLIENT_ID = "1347834940380676156"  # Public VLC RPC Client ID

DEFAULT_CONFIG = {
    "client_id": DEFAULT_CLIENT_ID,
    "vlc_host": "localhost",
    "vlc_port": 8080,
    "vlc_password": "",
    "update_interval": 2,
    "large_image_key": "vlc",
    "large_image_text": "VLC Media Player",
    "small_image_key": "play",
    "small_image_text": "Playing",
    "small_image_paused_key": "pause",
    "small_image_paused_text": "Paused"
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            # Ensure all keys exist
            for k, v in DEFAULT_CONFIG.items():
                if k not in config:
                    config[k] = v
            return config
    except Exception as e:
        console.print(f"[red]Error loading config.json: {e}. Restoring defaults.[/red]")
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        console.print(f"[red]Failed to save config.json: {e}[/red]")

def run_setup_wizard():
    console.clear()
    title_text = Text("VLC Discord RPC Setup Wizard", style="bold magenta", justify="center")
    console.print(Panel(title_text, border_style="magenta"))
    
    instructions = (
        "[bold yellow]To connect this script to VLC, you must enable VLC's Web Interface:[/]\n\n"
        "1. Open VLC Media Player.\n"
        "2. Click [bold cyan]Tools -> Preferences[/] (or press [bold]Ctrl + P[/]).\n"
        "3. At the bottom left, under [bold]Show settings[/], select [bold]All[/].\n"
        "4. Expand [bold]Interface[/] in the left panel, and click on [bold]Main interfaces[/].\n"
        "5. Check the [bold cyan]Web[/] checkbox.\n"
        "6. Expand [bold]Main interfaces[/] and click on [bold]Lua[/].\n"
        "7. Enter a password in the [bold cyan]Lua HTTP -> Password[/] field (leave the username blank).\n"
        "8. Click [bold green]Save[/] and [bold red]RESTART VLC[/] for changes to take effect.\n"
    )
    console.print(Panel(instructions, title="VLC Configuration Guide", border_style="cyan"))

    config = load_config()
    
    # Prompt password
    password = ""
    while not password:
        password = console.input("[bold green]Enter the Lua HTTP Password you configured in VLC: [/]").strip()
        if not password:
            console.print("[red]Password cannot be empty.[/red]")
            
    port_input = console.input(f"[bold green]Enter VLC HTTP Port (Default: 8080): [/]").strip()
    port = int(port_input) if port_input.isdigit() else 8080
    
    host_input = console.input(f"[bold green]Enter VLC Host (Default: localhost): [/]").strip()
    host = host_input if host_input else "localhost"
    
    client_id_input = console.input(f"[bold green]Enter Discord Application Client ID (Press Enter for Default VLC App): [/]").strip()
    client_id = client_id_input if client_id_input else DEFAULT_CLIENT_ID

    config["vlc_password"] = password
    config["vlc_port"] = port
    config["vlc_host"] = host
    config["client_id"] = client_id
    
    # Verify connection
    console.print("\n[yellow]Testing connection to VLC Media Player...[/yellow]")
    url = f"http://{host}:{port}/requests/status.json"
    try:
        response = requests.get(url, auth=HTTPBasicAuth('', password), timeout=3)
        if response.status_code == 200:
            console.print("[bold green]✓ Successfully connected to VLC Media Player![/]")
            save_config(config)
            time.sleep(2)
            return config
        elif response.status_code == 401:
            console.print("[bold red]✗ Connection unauthorized! Please double check your password in VLC.[/]")
        else:
            console.print(f"[bold red]✗ VLC returned status code {response.status_code}[/]")
    except requests.exceptions.ConnectionError:
        console.print("[bold red]✗ Failed to connect. Is VLC Media Player running and is the Web Interface enabled?[/]")
    except Exception as e:
        console.print(f"[bold red]✗ Connection test failed: {e}[/]")
        
    retry = console.input("\n[bold yellow]Would you like to save the settings anyway? (y/n): [/]").strip().lower()
    if retry == 'y':
        save_config(config)
        return config
    else:
        sys.exit("Setup cancelled.")

class VLCRPCManager:
    def __init__(self, config):
        self.config = config
        self.vlc_url = f"http://{config['vlc_host']}:{config['vlc_port']}/requests/status.json"
        self.password = config['vlc_password']
        self.client_id = config['client_id']
        self.update_interval = config['update_interval']
        
        self.rpc = None
        self.rpc_connected = False
        self.vlc_connected = False
        
        self.current_state = "idle"
        self.current_title = ""
        self.current_artist = ""
        self.current_album = ""
        self.current_time = 0
        self.current_length = 0
        self.current_volume = 0
        self.last_update_time = 0
        
        # Keep track of last presence update payload to reduce API spam
        self.last_presence_payload = {}
        
    def test_vlc_connection(self):
        try:
            response = requests.get(self.vlc_url, auth=HTTPBasicAuth('', self.password), timeout=1)
            if response.status_code == 200:
                self.vlc_connected = True
                return True
            elif response.status_code == 401:
                self.vlc_connected = False
                return "auth_failed"
        except requests.exceptions.RequestException:
            pass
        self.vlc_connected = False
        return False

    def fetch_vlc_status(self):
        try:
            response = requests.get(self.vlc_url, auth=HTTPBasicAuth('', self.password), timeout=1.5)
            if response.status_code == 200:
                self.vlc_connected = True
                data = response.json()
                
                self.current_state = data.get("state", "stopped")
                self.current_time = int(data.get("time", 0))
                self.current_length = int(data.get("length", 0))
                
                # Volume range in VLC API is usually 0 to 512, where 256 is 100%
                raw_volume = data.get("volume", 0)
                self.current_volume = int((raw_volume / 256.0) * 100) if raw_volume else 0
                
                meta = data.get("information", {}).get("category", {}).get("meta", {})
                self.current_title = meta.get("title") or meta.get("filename") or "Unknown Title"
                self.current_artist = meta.get("artist", "")
                self.current_album = meta.get("album", "")
                
                # If there is no title/filename at all but it is playing
                if not meta and self.current_state == "playing":
                    self.current_title = "Streaming Audio/Video"
                    
                return True
            elif response.status_code == 401:
                self.vlc_connected = False
                self.current_state = "auth_failed"
                return False
        except requests.exceptions.RequestException:
            self.vlc_connected = False
            self.current_state = "offline"
            return False
            
    def connect_discord(self):
        if self.rpc_connected:
            return True
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.rpc_connected = True
            return True
        except (DiscordNotFound, DiscordError, ConnectionRefusedError):
            self.rpc_connected = False
            self.rpc = None
            return False
        except Exception:
            self.rpc_connected = False
            self.rpc = None
            return False

    def disconnect_discord(self):
        if self.rpc:
            try:
                self.rpc.close()
            except Exception:
                pass
        self.rpc = None
        self.rpc_connected = False
        self.last_presence_payload = {}

    def update_presence(self):
        if not self.rpc_connected:
            if not self.connect_discord():
                return False

        # If VLC is stopped or offline, clear presence
        if self.current_state in ["stopped", "offline", "auth_failed"]:
            if self.last_presence_payload:
                try:
                    self.rpc.clear()
                    self.last_presence_payload = {}
                except Exception:
                    self.disconnect_discord()
            return True

        # Truncate details/state to fit Discord limits (max 128 characters)
        details = self.current_title
        if len(details) > 120:
            details = details[:117] + "..."

        # Format state
        if self.current_artist:
            state = f"by {self.current_artist}"
            if self.current_album:
                state += f" ({self.current_album})"
        else:
            state = "Local Media" if self.current_length > 0 else "Streaming"
            
        if len(state) > 120:
            state = state[:117] + "..."

        # Calculate time parameters
        start_time = None
        end_time = None
        
        # Discord expects float or int timestamps
        now = time.time()
        
        if self.current_state == "playing":
            # Start timestamp in discord represents elapsed time
            start_time = int(now - self.current_time)
            if self.current_length > 0:
                end_time = int(start_time + self.current_length)
                
            small_image = self.config["small_image_key"]
            small_text = self.config["small_image_text"]
        else:
            # Paused state
            state = f"Paused | {state}"
            if len(state) > 120:
                state = state[:117] + "..."
                
            small_image = self.config["small_image_paused_key"]
            small_text = self.config["small_image_paused_text"]

        payload = {
            "details": details,
            "state": state,
            "large_image": self.config["large_image_key"],
            "large_text": self.config["large_image_text"],
            "small_image": small_image,
            "small_text": small_text
        }
        
        # Only add start/end timers for playing state
        if start_time is not None:
            payload["start"] = start_time
        if end_time is not None:
            payload["end"] = end_time

        # Check if the presence payload has changed significantly
        # Discord RPC rate limits if we update too frequently with the exact same data
        if payload != self.last_presence_payload or (now - self.last_update_time) > 15:
            try:
                self.rpc.update(**payload)
                self.last_presence_payload = payload
                self.last_update_time = now
            except Exception:
                # Handle disconnection
                self.disconnect_discord()
                return False
        return True

def format_time(seconds):
    if seconds < 0:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def make_dashboard(manager):
    # Create the layout
    layout = Layout()
    
    # Split layout
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )
    
    # Header panel
    header_text = Text("VLC MEDIA PLAYER DISCORD RICH PRESENCE", style="bold magenta", justify="center")
    layout["header"].update(Panel(Align.center(header_text, vertical="middle"), border_style="magenta"))
    
    # Footer panel
    footer_text = Text("Ctrl+C to stop the script | Created by Antigravity AI", style="dim cyan", justify="center")
    layout["footer"].update(Panel(Align.center(footer_text, vertical="middle"), border_style="cyan"))
    
    # Body consists of status and media panels
    layout["body"].split_row(
        Layout(name="status", ratio=1),
        Layout(name="media", ratio=2)
    )
    
    # Status panel content
    status_table = Table.grid(padding=(0, 1))
    
    vlc_status_text = "[bold green]Connected[/]" if manager.vlc_connected else "[bold red]Disconnected[/]"
    if manager.current_state == "auth_failed":
        vlc_status_text = "[bold yellow]Auth Failed (Check Password)[/]"
        
    discord_status_text = "[bold green]Connected[/]" if manager.rpc_connected else "[bold red]Disconnected[/]"
    
    status_table.add_row(Text("VLC Status:", style="bold cyan"), Text(vlc_status_text))
    status_table.add_row(Text("VLC Host:", style="bold cyan"), Text(f"{manager.config['vlc_host']}:{manager.config['vlc_port']}"))
    status_table.add_row(Text("Discord RPC:", style="bold cyan"), Text(discord_status_text))
    status_table.add_row(Text("Update Interval:", style="bold cyan"), Text(f"{manager.update_interval}s"))
    
    layout["status"].update(Panel(
        Align.center(status_table, vertical="middle"), 
        title="Connections Status", 
        border_style="cyan"
    ))
    
    # Media panel content
    if not manager.vlc_connected:
        media_content = Align.center(
            Text("Waiting for VLC Media Player to run...\nMake sure Lua Web Interface is enabled.", style="bold yellow", justify="center"),
            vertical="middle"
        )
    elif manager.current_state == "stopped":
        media_content = Align.center(
            Text("VLC is Idle (Stopped)\nNo media loaded.", style="bold cyan", justify="center"),
            vertical="middle"
        )
    elif manager.current_state in ["playing", "paused"]:
        media_table = Table.grid(padding=(0, 1))
        
        # State tag
        state_tag = "[bold green]PLAYING[/]" if manager.current_state == "playing" else "[bold yellow]PAUSED[/]"
        
        media_table.add_row(Text("State:", style="bold cyan"), Text(state_tag))
        media_table.add_row(Text("Title:", style="bold cyan"), Text(manager.current_title, style="bold white", overflow="ellipsis"))
        
        if manager.current_artist:
            media_table.add_row(Text("Artist:", style="bold cyan"), Text(manager.current_artist, overflow="ellipsis"))
        if manager.current_album:
            media_table.add_row(Text("Album:", style="bold cyan"), Text(manager.current_album, overflow="ellipsis"))
            
        media_table.add_row(Text("Volume:", style="bold cyan"), Text(f"{manager.current_volume}%"))
        
        # Time and progress bar
        current_t = format_time(manager.current_time)
        total_t = format_time(manager.current_length) if manager.current_length > 0 else "Live Stream"
        time_text = f"{current_t} / {total_t}"
        
        if manager.current_length > 0:
            percentage = min(1.0, max(0.0, manager.current_time / manager.current_length))
            progress_bar = ProgressBar(total=100, completed=int(percentage * 100), width=30, pulse=False, complete_style="magenta")
            
            # Combine progress bar and time side by side
            progress_table = Table.grid(padding=(0, 2))
            progress_table.add_row(progress_bar, Text(time_text, style="white"))
            media_table.add_row(Text("Progress:", style="bold cyan"), progress_table)
        else:
            media_table.add_row(Text("Progress:", style="bold cyan"), Text(time_text, style="bold red"))
            
        media_content = Align.center(media_table, vertical="middle")
    else:
        media_content = Align.center(
            Text("Connecting to VLC HTTP API...", style="bold yellow", justify="center"),
            vertical="middle"
        )
        
    layout["media"].update(Panel(
        media_content,
        title="Current Media Info",
        border_style="magenta"
    ))
    
    return layout

def main():
    config = load_config()
    
    # If password is not configured, run the setup wizard
    if not config.get("vlc_password"):
        config = run_setup_wizard()
        
    manager = VLCRPCManager(config)
    
    # Initial status test
    vlc_test = manager.test_vlc_connection()
    if vlc_test == "auth_failed":
        console.print("[bold red]VLC Authentication Failed! The Lua password in config.json is incorrect.[/]")
        config = run_setup_wizard()
        manager = VLCRPCManager(config)
        
    console.print("[cyan]Initializing Discord RPC dashboard...[/cyan]")
    
    # Use Live panel to render the dashboard in real-time
    with Live(make_dashboard(manager), refresh_per_second=2, screen=True) as live:
        try:
            while True:
                # Fetch status from VLC
                manager.fetch_vlc_status()
                
                # If connected to VLC and in playing/paused status, update Discord RPC
                if manager.vlc_connected:
                    if manager.current_state in ["playing", "paused"]:
                        manager.update_presence()
                    else:
                        # Clear presence if VLC is idle/stopped
                        if manager.rpc_connected and manager.last_presence_payload:
                            manager.rpc.clear()
                            manager.last_presence_payload = {}
                else:
                    # VLC is offline, clear or disconnect Discord
                    if manager.rpc_connected:
                        manager.disconnect_discord()
                
                # Update dashboard view
                live.update(make_dashboard(manager))
                
                # Wait for update interval
                time.sleep(config["update_interval"])
                
        except KeyboardInterrupt:
            # Handle user exit gracefully
            live.stop()
            console.clear()
            console.print("[yellow]Disconnecting from Discord Rich Presence...[/yellow]")
            manager.disconnect_discord()
            console.print("[green]Goodbye![/green]")
            sys.exit(0)

if __name__ == "__main__":
    main()
