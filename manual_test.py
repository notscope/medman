#!/usr/bin/env python3
import os
import shutil
import tempfile
import subprocess
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw

def create_image(directory, name, size=(300, 300), color=(255, 0, 0), text=None):
    path = os.path.join(directory, name)
    # Use random noise to ensure pHash is distinct
    arr = np.random.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    # Blend with base color
    arr = (arr * 0.2 + np.array(color) * 0.8).astype(np.uint8)
    img = Image.fromarray(arr)
    
    d = ImageDraw.Draw(img)
    if text:
        d.text((10, 10), text, fill=(255, 255, 255))
    else:
        # Draw random distinct shape
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

def create_video(directory, name, duration=2, size=(320, 240), color=(0, 0, 255)):
    path = os.path.join(directory, name)
    fps = 24
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
    
    seed = sum(ord(c) for c in name)
    np.random.seed(seed)
    
    for i in range(fps * duration):
        frame = np.random.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        cv2.circle(frame, (i % size[0], i % size[1]), 50, color, -1)
        out.write(frame)
    out.release()
    return path

def main():
    print("=== MedMan Manual GUI Test Generator ===")
    test_dir = tempfile.mkdtemp(prefix="medman_manual_test_")
    print(f"[INFO] Created temporary test directory: {test_dir}")
    
    try:
        # --- Generate Data ---
        print("[INFO] Generating synthetic media...")

        # 1. Image Clusters
        # Cluster A: Exact duplicates
        img_a = create_image(test_dir, "clusterA_base.jpg", color=(100, 0, 0))
        shutil.copy(img_a, os.path.join(test_dir, "clusterA_copy.jpg"))

        # Cluster B: Visual duplicates (resized)
        img_b = create_image(test_dir, "clusterB_base.jpg", color=(0, 100, 0))
        img = Image.open(img_b)
        img.resize((150, 150)).save(os.path.join(test_dir, "clusterB_resized.jpg"))

        # Unique Images
        create_image(test_dir, "unique_1.jpg", color=(0, 0, 100))
        create_image(test_dir, "unique_2.jpg", color=(100, 100, 0))

        # 2. Video Clusters
        # Cluster C: Exact video duplicates
        vid_c = create_video(test_dir, "clusterC_base.mp4", color=(10, 10, 50))
        shutil.copy(vid_c, os.path.join(test_dir, "clusterC_copy.mp4"))

        # Cluster D: Visual video duplicates (different size/encoding simulation)
        # Note: True encoding diff is hard to simulate perfectly with opencv writers quickly, 
        # but we can make a "visually similar" one by just changing resolution slightly or noise seed if we wanted.
        # For now, let's just do another exact copy named differently to ensure GUI shows it.
        vid_d = create_video(test_dir, "clusterD_base.mp4", color=(0, 50, 50))
        shutil.copy(vid_d, os.path.join(test_dir, "clusterD_copy.mp4"))

        print("[INFO] Data generation complete.")
        print("[INFO] Launching MedMan in interactive mode...")
        print("       (Close the GUI window to finish the test)")
        
        # --- Run Main Program ---
        # Assuming main.py is in the current directory
        main_script = os.path.abspath("main.py")
        cmd = [sys.executable, main_script, test_dir, "--interactive", "--threshold", "0.8"]
        
        subprocess.run(cmd)

        print("\n[INFO] Test finished.")

    finally:
        # --- Cleanup ---
        print(f"[INFO] Cleaning up {test_dir}...")
        shutil.rmtree(test_dir)
        print("[INFO] Done.")

if __name__ == "__main__":
    main()
