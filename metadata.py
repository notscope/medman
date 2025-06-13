from PIL import Image
import cv2
import os

def get_image_metadata(path):
    try:
        with Image.open(path) as img:
            return img.size, os.path.getsize(path)
    except:
        return (0, 0), 0

def get_video_metadata(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return (0, 0), 0, 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    duration = frames / fps if fps > 0 else 0
    cap.release()
    return (width, height), duration, os.path.getsize(path)

def has_exif(path):
    try:
        img = Image.open(path)
        return hasattr(img, '_getexif') and img._getexif() is not None
    except:
        return False