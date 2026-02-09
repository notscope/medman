import os
import unittest
import tempfile
import shutil
from hashing import get_file_fingerprint, hash_file_sha256

class CorrectnessTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_fingerprint_vs_sha(self):
        """Verify that files with same fingerprint are indeed candidates, and different fingerprints mean different files."""
        p1 = os.path.join(self.test_dir, "file1.bin")
        p2 = os.path.join(self.test_dir, "file2.bin")
        p3 = os.path.join(self.test_dir, "file3.bin")
        
        # Create two identical files
        content = b"hello world" * 10000
        with open(p1, 'wb') as f: f.write(content)
        with open(p2, 'wb') as f: f.write(content)
        
        # Create a file with same size but different middle
        content_diff = b"hello world" * 5000 + b"diff" + b"hello world" * 4999 + b" "
        # Ensure same size
        content_diff = content_diff[:len(content)]
        with open(p3, 'wb') as f: f.write(content_diff)

        fp1 = get_file_fingerprint(p1)
        fp2 = get_file_fingerprint(p2)
        fp3 = get_file_fingerprint(p3)

        # Identical files must have identical fingerprints
        self.assertEqual(fp1, fp2)
        
        # p3 has same size and ends, so it might have same fingerprint (which is fine, it's a candidate)
        # But SHA must distinguish them
        sha1 = hash_file_sha256(p1)
        sha3 = hash_file_sha256(p3)
        self.assertNotEqual(sha1, sha3)

    def test_chunked_sha_identity(self):
        """Verify chunked SHA produces same result as standard SHA logic."""
        p = os.path.join(self.test_dir, "large.bin")
        content = os.urandom(1024 * 1024) # 1MB
        with open(p, 'wb') as f: f.write(content)
        
        import hashlib
        expected = hashlib.sha256(content).hexdigest()
        actual = hash_file_sha256(p)
        self.assertEqual(expected, actual)

if __name__ == "__main__":
    unittest.main()
