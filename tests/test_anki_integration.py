import os
import unittest
import requests
from main import AnkiHelper, Card

TEST_DIR = os.path.join(os.path.dirname(__file__), 'test_notes')

class TestAnkiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Check if Anki is running before running integration tests
        cls.anki_running = False
        try:
            response = requests.post("http://localhost:8765", json={"action": "version", "version": 6}, timeout=1)
            if response.status_code == 200 and "result" in response.json():
                cls.anki_running = True
                # Create a test deck to guarantee it exists
                requests.post("http://localhost:8765", json={
                    "action": "createDeck",
                    "version": 6,
                    "params": {"deck": "test_integration_deck"}
                }, timeout=1)
        except requests.exceptions.RequestException:
            pass

    def test_anki_connection_and_add_note(self):
        if not self.anki_running:
            self.skipTest("Anki is not running on http://localhost:8765. Skipping integration test.")
            
        helper = AnkiHelper(folder_path=TEST_DIR, deck_name='test_integration_deck', skip_submission=False)
        card = Card(front='example_title', back='example back', tags={'test'})
        
        # Verify Anki connection
        self.assertTrue(helper.check_anki_connection())
        
        # Check card posting functionality (either adds it or updates it, returns SUCCESS or SKIPPED)
        result = helper.post_card_to_deck(card)
        self.assertIn(result, ['SUCCESS', 'SKIPPED'])
