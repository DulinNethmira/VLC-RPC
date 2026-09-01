import sys

with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_rpc_worker = False
skip_mode = None

for i, line in enumerate(lines):
    if 'def rpc_worker(self):' in line:
        in_rpc_worker = True
        
    if not in_rpc_worker:
        new_lines.append(line)
        continue

    # Remove rpc initializations
    if 'asyncio.set_event_loop' in line or 'rpc = None' in line and 'current_client_id' not in line and 'rpc_backoff' not in line:
        continue
    if 'current_client_id = None' in line:
        continue
    if 'rpc_backoff =' in line or 'rpc_reconnect_at =' in line:
        continue
        
    # Start of connection / clear logic
    if 'if rpc and self.state_data["rpc_connected"]:' in line and skip_mode != 'skip_update':
        if i < 6000: # This is the first one around 5436
            # We replace this with our logic
            new_lines.append('            rpc_should_clear = not getattr(self, "rpc_enabled", True) or not self.state_data.get("vlc_connected") or self.state_data.get("playback_state") not in ["playing", "paused"]\n')
            new_lines.append('            if rpc_should_clear:\n')
            new_lines.append('                if getattr(self, "discord_manager", None):\n')
            new_lines.append('                    self.discord_manager.clear_activity(self.media_generation)\n')
            new_lines.append('            else:\n')
            skip_mode = 'skip_clear'
            continue
            
    if skip_mode == 'skip_clear':
        if 'else:' in line:
            # Reached the else block where kwargs starts
            skip_mode = None
            continue
        continue

    if 'last_kwargs = getattr(self, "_last_rpc_kwargs", {})' in line:
        # Start of the update block around 6112
        new_lines.append('                        if getattr(self, "discord_manager", None):\n')
        new_lines.append('                            self.discord_manager.submit_activity(self.media_generation, desired_client_id, kwargs)\n')
        skip_mode = 'skip_update'
        continue
        
    if skip_mode == 'skip_update':
        if 'if rpc and self.state_data["rpc_connected"]:' in line:
            # Start of the idle block around 6178
            skip_mode = 'skip_idle'
            new_lines.append('            if getattr(self, "discord_manager", None):\n')
            new_lines.append('                _idle_secs = time.time() - getattr(self.discord_manager, "last_update_time", 0)\n')
            new_lines.append('                if _idle_secs > 60 and self.discord_manager.current_kwargs:\n')
            new_lines.append('                    self.discord_manager.clear_activity(self.media_generation)\n')
            continue
        continue
        
    if skip_mode == 'skip_idle':
        if 'update_interval = self.config.get("update_interval", 2)' in line:
            skip_mode = None
            new_lines.append(line)
        continue
        
    # Exit loop shutdown hook
    if 'if self.state_data.get("exit_flag"):' in line:
        new_lines.append(line)
        new_lines.append('                if getattr(self, "discord_manager", None):\n')
        new_lines.append('                    self.discord_manager.stop()\n')
        continue

    # Removing desired_client_id checking block (lines 5425-5469)
    if 'if rpc and current_client_id != desired_client_id:' in line:
        skip_mode = 'skip_conn_check'
        continue
    if skip_mode == 'skip_conn_check':
        if 'if not rpc and time.time() >= rpc_reconnect_at:' in line:
            skip_mode = 'skip_conn_reconnect'
            continue
        continue
    if skip_mode == 'skip_conn_reconnect':
        if 'if rpc and self.state_data["rpc_connected"]:' in line:
            # End of conn block, transition into skip_clear
            new_lines.append('            rpc_should_clear = not getattr(self, "rpc_enabled", True) or not self.state_data.get("vlc_connected") or self.state_data.get("playback_state") not in ["playing", "paused"]\n')
            new_lines.append('            if rpc_should_clear:\n')
            new_lines.append('                if getattr(self, "discord_manager", None):\n')
            new_lines.append('                    self.discord_manager.clear_activity(self.media_generation)\n')
            new_lines.append('            else:\n')
            skip_mode = 'skip_clear'
            continue
        continue

    new_lines.append(line)

with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Patch applied successfully')
