import hashlib
from PIL import Image, ImageTk, UnidentifiedImageError
import imagehash
import cv2
from config import DEFAULT_VIDEO_FRAMES


def hash_file_sha256(path):
    try:
        with open(path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None

def hash_image_phash(path):
    try:
        img = Image.open(path).convert('RGB')
        return imagehash.phash(img)
    except UnidentifiedImageError:
        return None
    except Exception:
        return None
    
def hash_video_frames(path, sample_count=DEFAULT_VIDEO_FRAMES):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, frame_count // sample_count) if frame_count>0 else 1
    hashes = []
    idx = 0
    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        try:
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((128, 128))
            hashes.append(imagehash.phash(img))
        except:
            pass
        idx += step
        if len(hashes) >= sample_count:
            break
    cap.release()
    return hashes

def compare_video_hashes(hashes1, hashes2):
    if not hashes1 or not hashes2:
        return 0.0
    total = min(len(hashes1), len(hashes2))
    diffs = [abs(h1 - h2) for h1, h2 in zip(hashes1, hashes2)]
    sim = 1 - (sum(diffs) / (64.0 * total))
    return max(0.0, sim)