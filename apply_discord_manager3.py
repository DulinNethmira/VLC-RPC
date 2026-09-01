with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = lines[:5424]

new_lines.append('            desired_client_id = self.config.get("client_id", "").strip() or DEFAULT_CLIENT_ID\n')
new_lines.append('\n')
new_lines.append('            if getattr(self, "discord_manager", None):\n')
new_lines.append('                self.discord_manager.submit_activity(self.media_generation, desired_client_id, kwargs)\n')
new_lines.append('                _idle_secs = time.time() - getattr(self.discord_manager, "last_update_time", 0)\n')
new_lines.append('                if _idle_secs > 60 and self.discord_manager.current_kwargs:\n')
new_lines.append('                    self.discord_manager.clear_activity(self.media_generation)\n')
new_lines.append('\n')

# Append the rest starting from `update_interval`
new_lines.extend(lines[6285:6304])
new_lines.append('\n')
new_lines.append('        # Shutdown discord manager when worker loop exits\n')
new_lines.append('        if getattr(self, "discord_manager", None):\n')
new_lines.append('            self.discord_manager.stop()\n')
new_lines.append('\n')
new_lines.extend(lines[6304:])

with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("done")
