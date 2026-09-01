import re

with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    src = f.read()

# 1. Remove rpc initializations
src = re.sub(
    r'asyncio\.set_event_loop\(asyncio\.new_event_loop\(\)\)\s+rpc = None\s+current_client_id = None\s+last_track_key = None\s+rpc_backoff = 1\s+# seconds to wait before next reconnect attempt\s+rpc_reconnect_at = 0\.0\s+# earliest epoch time allowed for a reconnect',
    'last_track_key = None',
    src,
    flags=re.MULTILINE
)

# 2. Replace connection logic (lines starting around `desired_client_id = self.config.get...` to `self._last_rpc_cleared = False`)
conn_regex = re.compile(
    r'\s+desired_client_id = self\.config\.get\("client_id", ""\)\.strip\(\) or DEFAULT_CLIENT_ID\s+if rpc and current_client_id != desired_client_id:.*?(?=\s+processed = kwargs)',
    re.DOTALL
)

def repl_conn(m):
    return """
            desired_client_id = self.config.get("client_id", "").strip() or DEFAULT_CLIENT_ID
            
            # Send desired client id to discord manager
            # The submit_activity handles everything.
            
"""
src = conn_regex.sub(repl_conn, src)

# 3. Replace update logic (lines starting around `last_kwargs = getattr(self, "_last_rpc_kwargs", {})` to `rpc_backoff = min(rpc_backoff * 2, 30)`)
update_regex = re.compile(
    r'\s+last_kwargs = getattr\(self, "_last_rpc_kwargs", \{\}\)\s+if _is_significant_change\(last_kwargs, kwargs\):.*?(?=\s+if rpc and self\.state_data\["rpc_connected"\]:)',
    re.DOTALL
)

def repl_update(m):
    return """
                        # Submit to discord manager
                        self.discord_manager.submit_activity(self.media_generation, desired_client_id, kwargs)
"""
src = update_regex.sub(repl_update, src)


# 4. Replace idle clearing logic
idle_regex = re.compile(
    r'\s+if rpc and self\.state_data\["rpc_connected"\]:\s+_idle_secs = time\.time\(\) - getattr\(self, "_last_rpc_update_time", 0\)\s+if _idle_secs > 60:.*?(?=\s+time\.sleep\(1\.0\))',
    re.DOTALL
)

def repl_idle(m):
    return """
            if getattr(self, "discord_manager", None):
                _idle_secs = time.time() - getattr(self.discord_manager, "last_update_time", 0)
                if _idle_secs > 60 and self.discord_manager.current_kwargs:
                    self.discord_manager.clear_activity(self.media_generation)
"""
src = idle_regex.sub(repl_idle, src)

# 5. Add exit hook to rpc_worker loop
exit_regex = re.compile(r'(\s+if self\.state_data\.get\("exit_flag"\):)')
def repl_exit(m):
    return m.group(1) + """
                if getattr(self, "discord_manager", None):
                    self.discord_manager.stop()"""
src = exit_regex.sub(repl_exit, src)


with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.write(src)
print("Applied DiscordManager patch to vlc_discord_rpc_gui.py")
