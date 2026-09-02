import time
import threading
import uuid

class NotificationPriority:
    CRITICAL = 40
    HIGH = 30
    NORMAL = 20
    LOW = 10
    DEBUG = 0

class NotificationStatus:
    DISPLAYED = "DISPLAYED"
    SUPPRESSED = "SUPPRESSED"
    MERGED = "MERGED"
    QUEUED = "QUEUED"
    
class NotificationManager:
    def __init__(self):
        self._lock = threading.RLock()
        self.history = []
        # deduplication states: { dedup_key: {"last_time": time, "count": int, "queued_event": event} }
        self.dedup_state = {}
        # Cooldown per type (in seconds)
        self.cooldowns = {
            "media_detection": 5,
            "episode_change": 5,
            "anime_completed": 0,
            "rewatch": 0,
            "anilist_sync": 5,
            "sync_failure": 30,
            "recognition_failure": 60,
            "connection_recovery": 10,
            "connection_lost": 30,
            "default": 10
        }
    
    def send(self, type_id, title, message, priority, dedup_key, media=None, is_playing=False, notification_mode="Enabled", suppress_while_playing=True, show_toast_cb=None, log_cb=None, icon="info"):
        with self._lock:
            now = time.time()
            cooldown = self.cooldowns.get(type_id, self.cooldowns["default"])
            
            state = self.dedup_state.get(dedup_key, {"last_time": 0, "count": 0, "queued_event": None})
            
            # 1. Deduplication (Fixed Window)
            if now - state["last_time"] < cooldown:
                state["count"] += 1
                self.dedup_state[dedup_key] = state
                self._record_history(type_id, title, message, priority, media, NotificationStatus.MERGED)
                
                # Update queued event to the latest message so we can flush the most recent state
                if state["queued_event"]:
                    state["queued_event"]["message"] = message
                    
                if log_cb:
                    log_cb(f"[Notification] Merged duplicate ({state['count']}): {message}")
                return NotificationStatus.MERGED
            
            # 2. Evaluate Policy
            status = self._evaluate_policy(priority, is_playing, notification_mode, suppress_while_playing)
            
            # Reset dedup count since this is a new distinct event
            state["count"] = 1
            state["last_time"] = now
            
            if status == NotificationStatus.QUEUED:
                state["queued_event"] = {
                    "type_id": type_id, "title": title, "message": message, 
                    "priority": priority, "media": media, "icon": icon, "dedup_key": dedup_key
                }
            else:
                state["queued_event"] = None
                
            self.dedup_state[dedup_key] = state
            
            # 3. Action
            self._record_history(type_id, title, message, priority, media, status)
            
            if status == NotificationStatus.DISPLAYED:
                if show_toast_cb:
                    show_toast_cb(title, message, icon=icon)
            elif status == NotificationStatus.QUEUED:
                if log_cb:
                    log_cb(f"[Notification] Queued (playing): {message}")
            elif status == NotificationStatus.SUPPRESSED:
                if log_cb and priority >= NotificationPriority.NORMAL:
                    log_cb(f"[Notification] Suppressed ({notification_mode}): {message}")
            
            return status
            
    def _evaluate_policy(self, priority, is_playing, notification_mode, suppress_while_playing):
        if priority >= NotificationPriority.CRITICAL:
            if notification_mode == "Disabled":
                return NotificationStatus.SUPPRESSED
            return NotificationStatus.DISPLAYED
            
        if notification_mode == "Disabled" or notification_mode == "Critical Only":
            return NotificationStatus.SUPPRESSED
            
        if is_playing and suppress_while_playing:
            if priority <= NotificationPriority.LOW:
                return NotificationStatus.SUPPRESSED # Aggressively suppress LOW
            else:
                return NotificationStatus.QUEUED # Queue NORMAL/HIGH
                
        return NotificationStatus.DISPLAYED
        
    def _record_history(self, type_id, title, message, priority, media, status):
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "type": type_id,
            "title": title,
            "message": message,
            "severity": priority,
            "media": media,
            "status": status
        }
        self.history.insert(0, event)
        if len(self.history) > 500:
            self.history = self.history[:500]
            
    def flush_deferred(self, notification_mode="Enabled", show_toast_cb=None):
        with self._lock:
            for key, state in self.dedup_state.items():
                if state.get("queued_event"):
                    evt = state["queued_event"]
                    count = state["count"]
                    msg = evt["message"]
                    
                    if count > 1:
                        msg += f" (and {count-1} similar events)"
                    
                    if notification_mode not in ["Disabled", "Critical Only"]:
                        if show_toast_cb:
                            show_toast_cb(evt["title"], msg, icon=evt["icon"])
                        self._record_history(evt["type_id"], evt["title"], msg, evt["priority"], evt["media"], NotificationStatus.DISPLAYED)
                    
                    state["queued_event"] = None
                    state["count"] = 0
                    
    def get_history(self):
        with self._lock:
            return list(self.history)
            
    def clear_history(self):
        with self._lock:
            self.history.clear()
