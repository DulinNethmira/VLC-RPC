import unittest
from vlc_discord_rpc_gui import VlcDiscordRpc

class TestDashboardApi(unittest.TestCase):
    def test_dashboard_api(self):
        app = VlcDiscordRpc()
        # Test get_dashboard_stats doesn't crash on empty db
        app.db_path = ":memory:"
        app.init_db()
        stats = app.get_dashboard_stats()
        self.assertTrue("success" in stats)

if __name__ == "__main__":
    unittest.main()
