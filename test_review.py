import os
import tempfile
from PIL import Image
import cv2
import numpy as np

# Import the review functions from your module:
from main import review_image_pair, review_video_pair

# -- Test image GUI --
# Create two dummy images:
tmp1 = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
tmp2 = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
tmp1.close(); tmp2.close()
img1 = Image.new("RGB", (800, 600), color=(200, 50, 50))
img2 = Image.new("RGB", (600, 800), color=(50, 200, 50))
img1.save(tmp1.name)
img2.save(tmp2.name)

meta1 = ((800, 600), os.path.getsize(tmp1.name))
meta2 = ((600, 800), os.path.getsize(tmp2.name))
sim = 0.75

def on_decision_img(choice):
    print("Image GUI decision:", choice)

review_image_pair(tmp1.name, tmp2.name, meta1, meta2, sim, on_decision_img)
os.unlink(tmp1.name); os.unlink(tmp2.name)

# -- Test video GUI --
# Create two short dummy videos (2 seconds each)
# Parameters
width, height, fps = 320, 240, 24
duration_secs = 2

# Video 1
tmpv1 = "dummy1.mp4"
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out1 = cv2.VideoWriter(tmpv1, fourcc, fps, (width, height))
frame1 = np.full((height, width, 3), (50, 50, 200), dtype=np.uint8)
for _ in range(fps * duration_secs):
    out1.write(frame1)
out1.release()

# Video 2
tmpv2 = "dummy2.mp4"
out2 = cv2.VideoWriter(tmpv2, fourcc, fps, (width, height))
frame2 = np.full((height, width, 3), (200, 50, 50), dtype=np.uint8)
for _ in range(fps * duration_secs):
    out2.write(frame2)
out2.release()

meta_v1 = ((width, height), 2.0, os.path.getsize(tmpv1))
meta_v2 = ((width, height), 2.0, os.path.getsize(tmpv2))
sim_v = 0.5

def on_decision_vid(choice):
    print("Video GUI decision:", choice)

review_video_pair(tmpv1, tmpv2, meta_v1, meta_v2, sim_v, on_decision_vid)
os.remove(tmpv1); os.remove(tmpv2)
