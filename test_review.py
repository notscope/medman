import os
import tempfile
from PIL import Image
import cv2
import numpy as np
import random

from gui.window import review_image_pair, review_video_pair


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
# Create two short dummy videos
# Parameters
fps = 24
duration_secs = random.randint(3, 7)  # Random duration between 2 and 5 seconds
total_frames = fps * duration_secs

# Choose sizes
size1 = random.choice([(320, 240), (240, 320)])
size2 = random.choice([(320, 240), (240, 320)])

# Unpack so width1,height1 etc. are defined
width1, height1 = size1
width2, height2 = size2

def make_animated_video(filename, bg_color=(30, 30, 60), size=(320, 240)):
    """
    Create a video with multiple animated elements:
    - A circle bouncing horizontally and vertically.
    - A rectangle moving diagonally and bouncing off edges.
    - A rotating line at center.
    - Moving text across screen.
    """
    width, height = size
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    # Initial positions and velocities
    circ_radius = 20
    circ_pos = np.array([circ_radius, circ_radius], dtype=float)
    circ_vel = np.array([2.5, 1.8], dtype=float)  # pixels per frame

    rect_w, rect_h = 40, 30
    rect_pos = np.array([width - rect_w, 0], dtype=float)
    rect_vel = np.array([-2.2, 2.7], dtype=float)

    center = np.array([width//2, height//2])
    line_length = 50

    text = "TESTING"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_pos = np.array([-text_size[0], height//4], dtype=float)
    text_vel = np.array([3.0, 0], dtype=float)

    for i in range(total_frames):
        frame = np.full((height, width, 3), bg_color, dtype=np.uint8)

        # Update circle position
        circ_pos += circ_vel
        # Bounce off edges
        for dim in (0, 1):
            if circ_pos[dim] - circ_radius < 0:
                circ_pos[dim] = circ_radius
                circ_vel[dim] *= -1
            elif circ_pos[dim] + circ_radius > (width if dim == 0 else height):
                circ_pos[dim] = (width - circ_radius) if dim == 0 else (height - circ_radius)
                circ_vel[dim] *= -1
        cv2.circle(frame, tuple(circ_pos.astype(int)), circ_radius, (200, 100, 50), -1)

        # Update rectangle position
        rect_pos += rect_vel
        # Bounce rectangle off edges
        if rect_pos[0] < 0:
            rect_pos[0] = 0; rect_vel[0] *= -1
        elif rect_pos[0] + rect_w > width:
            rect_pos[0] = width - rect_w; rect_vel[0] *= -1
        if rect_pos[1] < 0:
            rect_pos[1] = 0; rect_vel[1] *= -1
        elif rect_pos[1] + rect_h > height:
            rect_pos[1] = height - rect_h; rect_vel[1] *= -1
        top_left = tuple(rect_pos.astype(int))
        bottom_right = tuple((rect_pos + [rect_w, rect_h]).astype(int))
        cv2.rectangle(frame, top_left, bottom_right, (50, 200, 100), -1)

        # Rotating line at center
        angle = (i / total_frames) * 360  # full rotation over duration
        theta = np.deg2rad(angle)
        pt1 = center + np.array([int(line_length * np.cos(theta)), int(line_length * np.sin(theta))])
        pt2 = center - np.array([int(line_length * np.cos(theta)), int(line_length * np.sin(theta))])
        cv2.line(frame, tuple(pt1.astype(int)), tuple(pt2.astype(int)), (255, 255, 255), 2)

        # Moving text
        text_pos += text_vel
        if text_pos[0] > width:
            text_pos[0] = -text_size[0]  # wrap around
        pos = tuple(text_pos.astype(int))
        cv2.putText(frame, text, pos, font, font_scale, (255, 200, 50), thickness, cv2.LINE_AA)

        out.write(frame)

    out.release()

# Usage example:
if __name__ == "__main__":
    tmpv1 = "animated1.mp4"
    tmpv2 = "animated2.mp4"
    make_animated_video(tmpv1, bg_color=(30, 30, 60), size=size1)
    make_animated_video(tmpv2, bg_color=(60, 30, 30), size=size2)
    # Now call your review_video_pair:
    meta_v1 = ((width1, height1), duration_secs, os.path.getsize(tmpv1))
    meta_v2 = ((width2, height2), duration_secs, os.path.getsize(tmpv2))
    sim_v = 0.5
    def on_decision_vid(choice):
        print("Video GUI decision:", choice)
    review_video_pair(tmpv1, tmpv2, meta_v1, meta_v2, sim_v, on_decision_vid)
    os.remove(tmpv1)
    os.remove(tmpv2)