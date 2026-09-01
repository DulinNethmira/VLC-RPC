import sys

with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'asyncio.set_event_loop(asyncio.new_event_loop())' in line:
        continue
    if 'rpc = None' in line and 'current_client_id = None' not in line and 'rpc_backoff' not in line:
        # We might have other rpc=None, let's just skip the specific block at the start of rpc_worker
        pass
        
    if 'desired_client_id = self.config.get("client_id"' in line:
        skip = True
        new_lines.append(line)
        new_lines.append('            # DiscordManager now handles connection asynchronously\n')
        continue
        
    if skip:
        # Check where to stop skipping for the connection block
        if 'if rpc and self.state_data["rpc_connected"]:' in line:
            # We reached the end of connection block, now we are at update/clear block!
            # We also need to skip the update block. Wait, the `if rpc and self.state_data...` block handles update!
            # The line `if getattr(self, "_last_rpc_cleared", False):` is inside this.
            pass
            
        if 'update_interval = self.config.get("update_interval", 2)' in line:
            skip = False
            # Insert the new discord manager logic before the sleep
            new_lines.append("""
            if getattr(self, "discord_manager", None):
                # Submit activity
                self.discord_manager.submit_activity(self.media_generation, desired_client_id, kwargs)
                
                # Check idle to clear
                _idle_secs = time.time() - getattr(self.discord_manager, "last_update_time", 0)
                if _idle_secs > 60 and self.discord_manager.current_kwargs:
                    self.discord_manager.clear_activity(self.media_generation)
""")
            new_lines.append(line)
        continue
        
    new_lines.append(line)

with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("done")
