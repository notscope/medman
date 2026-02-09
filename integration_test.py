#!/usr/bin/env python3
import os
import shutil
import tempfile
import unittest
import cv2
import numpy as np
from PIL import Image, ImageDraw
import argparse
from clustering import cluster_images, cluster_videos
from hashing import hash_file_sha256, hash_image_phash, hash_video_frames, compare_video_hashes

class TestMedManIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.duplicates_dir = os.path.join(self.test_dir, "duplicates")
        os.makedirs(self.duplicates_dir, exist_ok=True)
        print(f"\n[INFO] Created temp dir: {self.test_dir}")

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)
        print(f"[INFO] Removed temp dir: {self.test_dir}")

    def create_image(self, name, size=(100, 100), color=(255, 0, 0), text=None):
        path = os.path.join(self.test_dir, name)
        # Use random noise to ensure pHash is distinct
        arr = np.random.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        # Blend with base color
        arr = (arr * 0.2 + np.array(color) * 0.8).astype(np.uint8)
        img = Image.fromarray(arr)
        
        d = ImageDraw.Draw(img)
        # Draw a big X or random text to ensure structure
        if text:
            d.text((10, 10), text, fill=(255, 255, 255))
        else:
            # Draw random distinct shape based on name hash or something deterministic but different
            seed = sum(ord(c) for c in name)
            np.random.seed(seed)
            x0 = np.random.randint(0, size[0])
            y0 = np.random.randint(0, size[1])
            x1 = np.random.randint(0, size[0])
            y1 = np.random.randint(0, size[1])
            d.rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], 
                        fill=(np.random.randint(0,255), np.random.randint(0,255), np.random.randint(0,255)))
        img.save(path)
        return path

    def create_video(self, name, duration=2, size=(320, 240), color=(0, 0, 255)):
        path = os.path.join(self.test_dir, name)
        fps = 24
        out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
        
        # Determine unique seed from name
        seed = sum(ord(c) for c in name)
        np.random.seed(seed)
        
        for i in range(fps * duration):
            # Noisy frame
            frame = np.random.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
            # Add moving object to ensure temporal structure (though pHash is per frame)
            # Just drawing distinct structure is enough
            cv2.circle(frame, (i % size[0], i % size[1]), 50, color, -1)
            out.write(frame)
        out.release()
        return path

    def test_image_deduplication_exact(self):
        print("[TEST] Testing Exact Image Duplicates (SHA-256)...")
        # 1. Create base image
        img1_path = self.create_image("img_base.jpg", color=(100, 0, 0))
        
        # 2. Create exact duplicate (copy)
        img2_path = os.path.join(self.test_dir, "img_copy.jpg")
        shutil.copy(img1_path, img2_path)

        # 3. Create unique image
        self.create_image("img_unique.jpg", color=(0, 100, 0))

        # Run clustering
        image_paths = [
            os.path.join(self.test_dir, f) 
            for f in os.listdir(self.test_dir) 
            if f.endswith(('.jpg', '.png'))
        ]
        
        # We need to simulate how main.py calls this.
        # Use single worker to avoid multiprocessing hangs in test environment
        clusters = cluster_images(image_paths, threshold=0.9, sha_workers=1, phash_workers=1)

        # Assertions
        self.assertEqual(len(clusters), 1, "Should find exactly 1 cluster for identical images")
        cluster = clusters[0]
        self.assertEqual(len(cluster), 2, "Cluster should contain 2 files")
        self.assertIn(img1_path, cluster)
        self.assertIn(img2_path, cluster)
        print("[PASS] Exact image duplication detected.")

    def test_image_deduplication_visual(self):
        print("[TEST] Testing Visual Image Similarity (pHash)...")
        # 1. Base image
        img1_path = self.create_image("vis_base.jpg", size=(200, 200), color=(50, 50, 200), text="Test")

        # 2. Similar image (resize)
        img2_path = os.path.join(self.test_dir, "vis_small.jpg")
        img = Image.open(img1_path)
        img.resize((100, 100)).save(img2_path)

        # 3. Distinct image
        self.create_image("vis_other.jpg", color=(200, 50, 50))

        image_paths = [img1_path, img2_path, os.path.join(self.test_dir, "vis_other.jpg")]
        
        # Use single worker to avoid multiprocessing hangs
        clusters = cluster_images(image_paths, threshold=0.8, sha_workers=1, phash_workers=1)

        self.assertEqual(len(clusters), 1, "Should detect resized image as duplicate")
        self.assertEqual(len(clusters[0]), 2)
        print("[PASS] Visual image similarity detected.")

    def test_video_deduplication(self):
        print("[TEST] Testing Video Deduplication...")
        # 1. Base video
        v1_path = self.create_video("vid_1.mp4", color=(10, 10, 10))
        
        # 2. Duplicate video (copy)
        v2_path = os.path.join(self.test_dir, "vid_copy.mp4")
        shutil.copy(v1_path, v2_path)

        # 3. Unique video
        self.create_video("vid_unique.mp4", color=(200, 200, 200))

        video_paths = [
            os.path.join(self.test_dir, f)
            for f in os.listdir(self.test_dir)
            if f.endswith('.mp4')
        ]

        # Use single worker
        clusters = cluster_videos(video_paths, threshold=0.9, sample_count=10, sha_workers=1, phash_workers=1)

        self.assertEqual(len(clusters), 1, "Should detect identical videos")
        self.assertEqual(len(clusters[0]), 2)
        print("[PASS] Video deduplication detected.")

if __name__ == "__main__":
    unittest.main()
