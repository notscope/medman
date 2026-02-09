import os
import cv2
from hashing import hash_video_frames

def test_low_res_hashing():
    # Find a video file in the system or use a dummy if none found
    # For now, let's just use one from the user's project if possible, 
    # but we don't have sample media.
    # We can create a dummy video with OpenCV.
    
    dummy_path = "test_video.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(dummy_path, fourcc, 20.0, (640, 480))
    for i in range(100):
        frame = cv2.imread(os.path.join("static", "favicon.ico")) # Just some data
        if frame is None:
            import numpy as np
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        out.write(frame)
    out.release()
    
    print(f"Testing hashing on {dummy_path}...")
    hashes = hash_video_frames(dummy_path, sample_count=5)
    print(f"Got {len(hashes)} hashes.")
    
    if len(hashes) == 5:
        print("SUCCESS: Low-res hashing produced expected number of hashes.")
    else:
        print(f"FAILURE: Expected 5 hashes, got {len(hashes)}.")
    
    os.remove(dummy_path)

if __name__ == "__main__":
    test_low_res_hashing()
