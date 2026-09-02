import unittest
import time
import threading
from notification_manager import NotificationManager, NotificationPriority, NotificationStatus

class TestNotificationManager(unittest.TestCase):
    def setUp(self):
        self.manager = NotificationManager()
        # Override cooldowns for faster testing
        self.manager.cooldowns = {
            "connection_lost": 0.5,
            "default": 0.5
        }
        self.toast_calls = []
        self.log_calls = []
        
        self.show_toast_cb = lambda title, msg, icon: self.toast_calls.append((title, msg, icon))
        self.log_cb = lambda msg: self.log_calls.append(msg)

    def test_duplicate_suppression_and_cooldown(self):
        # 1st call
        status1 = self.manager.send("connection_lost", "Error", "Lost connection", NotificationPriority.NORMAL, "conn_lost", 
                          show_toast_cb=self.show_toast_cb, log_cb=self.log_cb)
        self.assertEqual(status1, NotificationStatus.DISPLAYED)
        self.assertEqual(len(self.toast_calls), 1)
        
        # 2nd call (duplicate, within cooldown)
        status2 = self.manager.send("connection_lost", "Error", "Lost connection", NotificationPriority.NORMAL, "conn_lost", 
                          show_toast_cb=self.show_toast_cb, log_cb=self.log_cb)
        self.assertEqual(status2, NotificationStatus.MERGED)
        self.assertEqual(len(self.toast_calls), 1) # Toast not called again
        
        # Wait for cooldown
        time.sleep(0.6)
        
        # 3rd call (after cooldown)
        status3 = self.manager.send("connection_lost", "Error", "Lost connection", NotificationPriority.NORMAL, "conn_lost", 
                          show_toast_cb=self.show_toast_cb, log_cb=self.log_cb)
        self.assertEqual(status3, NotificationStatus.DISPLAYED)
        self.assertEqual(len(self.toast_calls), 2)
        
    def test_suppression_while_playing(self):
        status = self.manager.send("episode_change", "Update", "Ep 2", NotificationPriority.NORMAL, "ep_change", 
                          is_playing=True, show_toast_cb=self.show_toast_cb)
        self.assertEqual(status, NotificationStatus.QUEUED)
        self.assertEqual(len(self.toast_calls), 0)
        
        # Flush deferred
        self.manager.flush_deferred(show_toast_cb=self.show_toast_cb)
        self.assertEqual(len(self.toast_calls), 1)

    def test_critical_override(self):
        # Critical bypasses playing suppression
        status = self.manager.send("error", "Critical", "Crash!", NotificationPriority.CRITICAL, "crash", 
                          is_playing=True, show_toast_cb=self.show_toast_cb)
        self.assertEqual(status, NotificationStatus.DISPLAYED)
        self.assertEqual(len(self.toast_calls), 1)
        
        # Critical DOES NOT bypass "Disabled" mode
        status2 = self.manager.send("error", "Critical", "Crash!", NotificationPriority.CRITICAL, "crash2", 
                          notification_mode="Disabled", show_toast_cb=self.show_toast_cb)
        self.assertEqual(status2, NotificationStatus.SUPPRESSED)

    def test_thread_safety(self):
        threads = []
        for i in range(10):
            t = threading.Thread(target=self.manager.send, args=("test", "T", f"Msg {i}", NotificationPriority.NORMAL, "key1"))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        history = self.manager.get_history()
        # 1 Displayed, 9 Merged = 10 total history events recorded safely
        self.assertEqual(len(history), 10)
        
        counts = [e["status"] for e in history]
        self.assertEqual(counts.count(NotificationStatus.DISPLAYED), 1)
        self.assertEqual(counts.count(NotificationStatus.MERGED), 9)

if __name__ == '__main__':
    unittest.main()
