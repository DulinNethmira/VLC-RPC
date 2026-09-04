import unittest
from metadata_engine import MetadataEngine, MediaIdentity

class TestMetadataParser(unittest.TestCase):
    def test_overlord(self):
        m = MetadataEngine.parse_filename("Overlord II E10.mkv")
        self.assertEqual(m.title, "Overlord II")
        self.assertEqual(m.season, 2)
        self.assertEqual(m.episode, 10)

    def test_one_piece(self):
        m = MetadataEngine.parse_filename("One Piece E1175.mkv")
        self.assertEqual(m.title, "One Piece")
        self.assertEqual(m.episode, 1175)

    def test_mushoku(self):
        m = MetadataEngine.parse_filename("Mushoku Tensei Jobless Reincarnation Season 3 Episode 10.mkv")
        self.assertEqual(m.title, "Mushoku Tensei Jobless Reincarnation")
        self.assertEqual(m.season, 3)
        self.assertEqual(m.episode, 10)
        
    def test_blood_blockade(self):
        m = MetadataEngine.parse_filename("Blood Blockade Battlefront S2E12.mkv")
        self.assertEqual(m.title, "Blood Blockade Battlefront")
        self.assertEqual(m.season, 2)
        self.assertEqual(m.episode, 12)

    def test_rezero(self):
        m = MetadataEngine.parse_filename("Re:ZERO -Starting Life in Another World- Season 4 Episode 15.mkv")
        self.assertEqual(m.title, "Re:ZERO -Starting Life in Another World-")
        self.assertEqual(m.season, 4)
        self.assertEqual(m.episode, 15)

if __name__ == "__main__":
    unittest.main()
