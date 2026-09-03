import sys
import threading
import time
from collections import deque
import traceback
import hashlib
import json

with open('vlc_discord_rpc_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

diagnostics_code = """
from collections import deque
import traceback
import hashlib

class DiagnosticsManager:
    def __init__(self, backend_ref):
        self.backend_ref = backend_ref
        self.lock = threading.RLock()
        
        # Valid states: HEALTHY, DEGRADED, OFFLINE, ERROR, UNKNOWN
        self.components = {
            "vlc": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0},
            "discord": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0},
            "anilist": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0},
            "metadata": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0},
            "gemini": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0},
            "cache": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0},
            "artwork": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0},
            "database": {"state": "UNKNOWN", "last_event": "Initializing", "last_success": None, "last_failure": None, "last_state_change": time.time(), "pending": 0}
        }
        
        self.timeline = deque(maxlen=200)
        self.errors = {}
        self.start_time = time.time()
        self.log_event("Diagnostics Center initialized", component="system")

    def set_state(self, component, state, event_msg=None, is_success=False, is_failure=False):
        with self.lock:
            if component not in self.components:
                return
            now = time.time()
            comp_data = self.components[component]
            
            if comp_data["state"] != state:
                comp_data["last_state_change"] = now
                comp_data["state"] = state
                if event_msg:
                    self.log_event(f"State changed to {state}: {event_msg}", component=component)
            
            if event_msg:
                comp_data["last_event"] = event_msg
            if is_success:
                comp_data["last_success"] = now
            if is_failure:
                comp_data["last_failure"] = now

    def set_pending(self, component, count):
        with self.lock:
            if component in self.components:
                self.components[component]["pending"] = count

    def log_event(self, message, component=None):
        with self.lock:
            self.timeline.append({
                "timestamp": time.time(),
                "component": component or "system",
                "message": message
            })

    def report_error(self, component, error_type, message, details=None, exc_info=None):
        with self.lock:
            now = time.time()
            
            error_key = f"{component}:{error_type}:{message}"
            error_hash = hashlib.md5(error_key.encode('utf-8')).hexdigest()
            
            if error_hash in self.errors:
                self.errors[error_hash]["count"] += 1
                self.errors[error_hash]["last_seen"] = now
                if details:
                    self.errors[error_hash]["details"] = details
            else:
                tb_str = None
                if exc_info:
                    try:
                        tb_str = "".join(traceback.format_exception(*exc_info))
                    except:
                        pass
                
                self.errors[error_hash] = {
                    "first_seen": now,
                    "last_seen": now,
                    "count": 1,
                    "component": component,
                    "type": error_type,
                    "message": message,
                    "details": details,
                    "traceback": tb_str
                }
            
            # Prune old errors if it grows too large (prevent memory leak)
            if len(self.errors) > 100:
                # Remove 20 oldest by last_seen
                sorted_keys = sorted(self.errors.keys(), key=lambda k: self.errors[k]["last_seen"])
                for k in sorted_keys[:20]:
                    del self.errors[k]

    def get_state(self):
        with self.lock:
            # Return a safe copy of the state
            sorted_errors = sorted(self.errors.values(), key=lambda x: x["last_seen"], reverse=True)
            return {
                "start_time": self.start_time,
                "uptime": time.time() - self.start_time,
                "components": {k: v.copy() for k, v in self.components.items()},
                "timeline": list(self.timeline),
                "errors": sorted_errors
            }

    def run_self_test(self):
        # Safe read-only tests for components
        threading.Thread(target=self._run_self_test_bg, daemon=True).start()
        return {"status": "started", "message": "Self-test sequence started in background"}

    def _run_self_test_bg(self):
        self.log_event("Running self-test sequence", component="system")
        
        # 1. Test VLC
        try:
            from requests.auth import HTTPBasicAuth
            import requests
            url = f"http://{self.backend_ref.config.get('vlc_host', 'localhost')}:{self.backend_ref.config.get('vlc_port', 8080)}/requests/status.json"
            auth = HTTPBasicAuth('', self.backend_ref.config.get("vlc_password", ""))
            r = requests.get(url, auth=auth, timeout=3)
            if r.status_code == 200:
                self.set_state("vlc", "HEALTHY", "Self-test: Connection successful", is_success=True)
            else:
                self.set_state("vlc", "DEGRADED", f"Self-test: HTTP {r.status_code}", is_failure=True)
        except Exception as e:
            self.report_error("vlc", "SelfTestError", str(e))
            self.set_state("vlc", "ERROR", f"Self-test failed: {str(e)}", is_failure=True)
            
        # 2. Test Discord
        if getattr(self.backend_ref, "discord_manager", None):
            dm = self.backend_ref.discord_manager
            if dm.state == "CONNECTED":
                self.set_state("discord", "HEALTHY", "Self-test: RPC Connected", is_success=True)
            else:
                self.set_state("discord", "OFFLINE", f"Self-test: Discord is {dm.state}")
        
        # 3. Test Database
        try:
            with self.backend_ref._db_lock:
                cursor = self.backend_ref.db_conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM history")
                count = cursor.fetchone()[0]
            self.set_state("database", "HEALTHY", f"Self-test: Read OK, {count} records", is_success=True)
        except Exception as e:
            self.report_error("database", "SelfTestError", str(e))
            self.set_state("database", "ERROR", "Database check failed", is_failure=True)
            
        # 4. Test Cache
        try:
            import os
            import json
            cache_file = self.backend_ref.CACHE_FILE
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.set_state("cache", "HEALTHY", f"Self-test: Loaded {len(data)} items", is_success=True)
            else:
                self.set_state("cache", "HEALTHY", "Self-test: No cache file yet", is_success=True)
        except Exception as e:
            self.report_error("cache", "SelfTestError", str(e))
            self.set_state("cache", "ERROR", "Cache check failed", is_failure=True)
            
        # 5. Test AniList (Read-only check, like viewer profile)
        if self.backend_ref.config.get("anilist_token"):
            try:
                query = '''
                query {
                    Viewer {
                        id
                        name
                    }
                }
                '''
                headers = {'Authorization': 'Bearer ' + self.backend_ref.config.get("anilist_token")}
                import requests
                r = requests.post("https://graphql.anilist.co", json={'query': query}, headers=headers, timeout=5)
                if r.status_code == 200:
                    self.set_state("anilist", "HEALTHY", "Self-test: API auth successful", is_success=True)
                else:
                    self.report_error("anilist", "SelfTestError", f"API returned {r.status_code}")
                    self.set_state("anilist", "DEGRADED", f"API returned {r.status_code}", is_failure=True)
            except Exception as e:
                self.report_error("anilist", "SelfTestError", str(e))
                self.set_state("anilist", "ERROR", f"Self-test failed: {str(e)}", is_failure=True)
        else:
            self.set_state("anilist", "UNKNOWN", "Self-test: Not logged in")
            
        # 6. Test Gemini (Read-only check, get models)
        if self.backend_ref.config.get("gemini_api_key"):
            try:
                import requests
                key = self.backend_ref.config.get("gemini_api_key")
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    self.set_state("gemini", "HEALTHY", "Self-test: API available", is_success=True)
                else:
                    self.report_error("gemini", "SelfTestError", f"API returned {r.status_code}")
                    self.set_state("gemini", "DEGRADED", f"API returned {r.status_code}", is_failure=True)
            except Exception as e:
                self.report_error("gemini", "SelfTestError", str(e))
                self.set_state("gemini", "ERROR", f"Self-test failed: {str(e)}", is_failure=True)
        else:
            self.set_state("gemini", "UNKNOWN", "Self-test: No API key")

        self.log_event("Self-test sequence completed", component="system")

    def export_diagnostics(self):
        import platform
        import sys
        import os
        import json
        
        with self.lock:
            state = self.get_state()
            
            # Build safe config
            safe_config = {}
            for k, v in self.backend_ref.config.items():
                if any(secret in k.lower() for secret in ["token", "password", "key", "secret"]):
                    safe_config[k] = "***REDACTED***"
                else:
                    safe_config[k] = v
                    
            export_data = {
                "version": getattr(self.backend_ref, "CURRENT_VERSION", "Unknown"),
                "os": platform.platform(),
                "python": sys.version,
                "diagnostics": state,
                "config": safe_config
            }
            
            export_path = os.path.abspath("diagnostics_export.json")
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
                
            return export_path
"""

split_index = content.find("class RPCBackend:")
new_content = content[:split_index] + diagnostics_code + "\n\n" + content[split_index:]

with open('vlc_discord_rpc_gui.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("DiagnosticsManager inserted.")
