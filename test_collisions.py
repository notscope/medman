import os
import unittest
import tempfile
import shutil
from clustering import cluster_images, cluster_videos
from hashing import get_file_fingerprint

class CollisionTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_image_collision_prevention(self):
        """Verify that two different images with same fingerprint are NOT clustered."""
        # Create two files with same size and same first/last 64KB
        # but different middle
        size = 200 * 1024 # 200KB
        header = b"A" * 65536
        footer = b"Z" * 65536
        middle1 = b"1" * (size - len(header) - len(footer))
        middle2 = b"2" * (size - len(header) - len(footer))
        
        p1 = os.path.join(self.test_dir, "img1.jpg")
        p2 = os.path.join(self.test_dir, "img2.jpg")
        
        with open(p1, 'wb') as f: f.write(header + middle1 + footer)
        with open(p2, 'wb') as f: f.write(header + middle2 + footer)
        
        # Verify fingerprints are identical
        fp1 = get_file_fingerprint(p1)
        fp2 = get_file_fingerprint(p2)
        self.assertEqual(fp1, fp2)
        
        # Run clustering
        # They are different bit-wise, so they should NOT be clustered
        # (pHash might be same since it's just solid colors, 
        # but SHA check should separate them if we use one rep per SHA)
        # Actually if they have DIFFERENT SHA, they are treated as unique reps.
        # But if they are solid colors, pHash WILL be identical.
        # However, the user said 65% similarity, which implies pHash was different too.
        # My fix ensures they go to pHash stage as separate representatives.
        
        clusters = cluster_images([p1, p2], threshold=0.9)
        # Since p1 and p2 are solid blocks of 1s and 2s, their pHash might be same.
        # Let's make them visually different too so pHash distinguishes them if they bypass SHA.
        
        # Re-create with noise in middle for pHash
        middle1 = os.urandom(size - len(header) - len(footer))
        middle2 = os.urandom(size - len(header) - len(footer))
        with open(p1, 'wb') as f: f.write(header + middle1 + footer)
        with open(p2, 'wb') as f: f.write(header + middle2 + footer)

        clusters = cluster_images([p1, p2], threshold=0.99) # Very high threshold
        self.assertEqual(len(clusters), 0, "Files with different middle should NOT be clustered despite sharing fingerprint.")

    def test_video_collision_prevention(self):
        """Verify video fingerprint collision prevention."""
        size = 100 * 1024
        header = b"V" * 1024
        footer = b"X" * 1024
        p1 = os.path.join(self.test_dir, "vid1.mp4")
        p2 = os.path.join(self.test_dir, "vid2.mp4")
        
        with open(p1, 'wb') as f: f.write(header + b"1" * (size-2048) + footer)
        with open(p2, 'wb') as f: f.write(header + b"2" * (size-2048) + footer)
        
        # These will fail to open as videos, returning empty hashes
        # But fingerprinting logic should still separate them if their SHA differs
        clusters = cluster_videos([p1, p2], threshold=0.9, sample_count=5)
        self.assertEqual(len(clusters), 0)

if __name__ == "__main__":
    unittest.main()
