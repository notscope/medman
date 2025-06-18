import hashlib
from PIL import Image, UnidentifiedImageError
import imagehash
import cv2
from tqdm import tqdm
from config import DEFAULT_VIDEO_FRAMES
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor

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
    step = max(1, frame_count // sample_count) if frame_count > 0 else 1
    
    hashes = []
    idx = 0
    processed = 0
    while processed < sample_count:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step == 0:
            small = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_AREA)
            img = Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
            hashes.append(imagehash.phash(img))
            processed += 1
        idx += 1
    
    cap.release()
    return hashes

def compare_video_hashes(hashes1, hashes2):
    if not hashes1 or not hashes2:
        return 0.0
    total = min(len(hashes1), len(hashes2))
    diffs = [abs(h1 - h2) for h1, h2 in zip(hashes1, hashes2)]
    sim = 1 - (sum(diffs) / (64.0 * total))
    return max(0.0, sim)

def hash_file_parallel(paths, max_workers=8):
    """Compute SHA256 for all paths in parallel, showing a tqdm progress bar."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(hash_file_sha256, p): p for p in paths}
        for future in tqdm(as_completed(future_to_path),
                           total=len(future_to_path),
                           desc="Parallel SHA hashing"):
            path = future_to_path[future]
            try:
                sha = future.result()
            except Exception:
                sha = None
            if sha is not None:
                results[path] = sha
    return results

def hash_image_parallel(paths, max_workers=8):
    """Compute image pHash for given paths in parallel, with tqdm."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(hash_image_phash, p): p for p in paths}
        for future in tqdm(as_completed(future_to_path),
                           total=len(future_to_path),
                           desc="Computing image pHash"):
            path = future_to_path[future]
            try:
                h = future.result()
            except Exception:
                h = None
            if h is not None:
                results[path] = h
    return results  # {path: pHash}

def _hash_video_wrapper(args):
    """Helper top-level function for ProcessPoolExecutor"""
    path, sample_count = args
    # import inside since executed in subprocess
    try:
        return path, hash_video_frames(path, sample_count)
    except Exception:
        return path, []

def hash_video_parallel(paths, sample_count, max_workers=4):
    """
    Compute video-frame hashes for all paths in parallel, with tqdm.
    Returns dict: path -> list of frame-hashes (possibly empty).
    """
    results = {}
    tasks = [(p, sample_count) for p in paths]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(_hash_video_wrapper, t): t[0] for t in tasks}
        for future in tqdm(as_completed(future_to_path),
                           total=len(future_to_path),
                           desc="Computing video pHash"):
            path = future_to_path[future]
            try:
                _, hlist = future.result()
            except Exception:
                hlist = []
            if hlist:
                results[path] = hlist
    return results  # dict: path -> list of hashes
