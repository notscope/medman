import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Create a mock for tkinter to simulate its absence or a missing display
class HeadlessClusteringTest(unittest.TestCase):
    
    @patch.dict(sys.modules, {'tkinter': None})
    def test_import_clustering_headless(self):
        """Verify that clustering.py can be imported even if tkinter is missing."""
        try:
            import clustering
            # If it imports without error, it's a success
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"clustering.py failed to import in headless mode: {e}")

    @patch('clustering.score_image', return_value=100)
    @patch('clustering.get_image_metadata', return_value=((100, 100), 1024))
    @patch('clustering.hash_image_phash', return_value=0)
    @patch('clustering.hash_file_sha256', return_value="abc")
    @patch('clustering.input', return_value='s') # Simulate 'Skip' in CLI
    @patch('os.path.exists', return_value=True)
    def test_handle_image_cluster_cli_fallback(self, mock_exists, mock_input, mock_sha, mock_phash, mock_meta, mock_score):
        """Verify that handle_image_cluster falls back to CLI if GUI is missing."""
        import clustering
        
        # We need to ensure gui.window import fails
        with patch.dict(sys.modules, {'gui.window': None}):
            cluster = ['/path/to/img1.jpg', '/path/to/img2.jpg']
            # Should not raise ImportError and should call input()
            clustering.handle_image_cluster(cluster, interactive=True, duplicates_dir='/tmp', cluster_index=1, cluster_total=1)
            mock_input.assert_called()

if __name__ == "__main__":
    unittest.main()
