import os
import hashlib
from PIL import Image, UnidentifiedImageError
import imagehash
import cv2
from tqdm import tqdm
from config import DEFAULT_VIDEO_FRAMES
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor

def get_file_fingerprint(path):
    """
    Returns a fast fingerprint (size, first_64kb_hash, last_64kb_hash).
    This allows identifying unique files instantly without reading the whole file.
    """
    try:
        size = os.path.getsize(path)
        if size == 0:
            return (0, "", "")
        
        with open(path, 'rb') as f:
            # First 64KB
            header = f.read(65536)
            h_start = hashlib.md5(header).hexdigest()
            
            # Last 64KB
            if size > 65536:
                f.seek(-65536, os.SEEK_END)
                footer = f.read(65536)
                h_end = hashlib.md5(footer).hexdigest()
            else:
                h_end = h_start
                
        return (size, h_start, h_end)
    except Exception:
        return None

def hash_file_sha256(path):
    """Compute SHA256 in chunks to be memory efficient and faster for large files."""
    sha256 = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            while True:
                data = f.read(65536) # 64KB chunks
                if not data:
                    break
                sha256.update(data)
        return sha256.hexdigest()
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
    # Disable OpenCV internal threading for this process to avoid contention
    # when running in parallel via ProcessPoolExecutor.
    cv2.setNumThreads(0)
    
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return []

    # Strategy: Request low-resolution frames from the decoder (160x120)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 160)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 120)

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        return []

    indices = [int(i * (frame_count - 1) / (sample_count - 1)) if sample_count > 1 else 0 for i in range(sample_count)]
    
    hashes = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        
        if not ret or frame is None:
            continue
        
        # 1. Convert to grayscale early in OpenCV
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 2. Resize to a small size in OpenCV (32x32 is plenty for pHash)
        # Using INTER_NEAREST for maximum speed
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_NEAREST)
        
        # 3. Convert to PIL for imagehash
        img = Image.fromarray(small)
        hashes.append(imagehash.phash(img))
    
    cap.release()
    return hashes

def compare_video_hashes(hashes1, hashes2):
    if not hashes1 or not hashes2:
        return 0.0
    total = min(len(hashes1), len(hashes2))
    diffs = [abs(h1 - h2) for h1, h2 in zip(hashes1, hashes2)]
    sim = 1 - (sum(diffs) / (64.0 * total))
    return max(0.0, sim)

def hash_fingerprint_parallel(paths, max_workers=8, progress_callback=None):
    """Compute fingerprints (size+md5_ends) for all paths in parallel."""
    results = {}
    total = len(paths)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(get_file_fingerprint, p): p for p in paths}
        for i, future in enumerate(tqdm(as_completed(future_to_path),
                           total=total,
                           desc="Fingerprinting files"), 1):
            path = future_to_path[future]
            try:
                res = future.result()
            except Exception:
                res = None
            if res is not None:
                results[path] = res
            if progress_callback:
                progress_callback(i, total)
    return results

def hash_file_parallel(paths, max_workers=8, progress_callback=None):
    """Compute SHA256 for all paths in parallel, using chunked reading."""
    results = {}
    total = len(paths)
    if total == 0: return {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(hash_file_sha256, p): p for p in paths}
        for i, future in enumerate(tqdm(as_completed(future_to_path),
                           total=total,
                           desc="Parallel SHA hashing"), 1):
            path = future_to_path[future]
            try:
                sha = future.result()
            except Exception:
                sha = None
            if sha is not None:
                results[path] = sha
            if progress_callback:
                progress_callback(i, total)
    return results

def _hash_image_wrapper(path):
    """Helper for ProcessPoolExecutor"""
    try:
        return path, hash_image_phash(path)
    except Exception:
        return path, None

def hash_image_parallel(paths, max_workers=4, progress_callback=None):
    """Compute image pHash in parallel using processes to bypass GIL."""
    results = {}
    total = len(paths)
    if total == 0: return {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(_hash_image_wrapper, p): p for p in paths}
        for i, future in enumerate(tqdm(as_completed(future_to_path),
                           total=total,
                           desc="Computing image pHash"), 1):
            path = future_to_path[future]
            try:
                _, h = future.result()
            except Exception:
                h = None
            if h is not None:
                results[path] = h
            if progress_callback:
                progress_callback(i, total)
    return results  # {path: pHash}

def _hash_video_wrapper(args):
    """Helper top-level function for ProcessPoolExecutor"""
    path, sample_count = args
    # import inside since executed in subprocess
    try:
        return path, hash_video_frames(path, sample_count)
    except Exception:
        return path, []

def hash_video_parallel(paths, sample_count, max_workers=4, progress_callback=None):
    """
    Compute video-frame hashes for all paths in parallel, with tqdm.
    Returns dict: path -> list of frame-hashes (possibly empty).
    """
    results = {}
    total = len(paths)
    if total == 0: return {}
    tasks = [(p, sample_count) for p in paths]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {executor.submit(_hash_video_wrapper, t): t[0] for t in tasks}
        for i, future in enumerate(tqdm(as_completed(future_to_path),
                           total=total,
                           desc="Computing video pHash"), 1):
            path = future_to_path[future]
            try:
                _, hlist = future.result()
            except Exception:
                hlist = []
            if hlist:
                results[path] = hlist
            if progress_callback:
                progress_callback(i, total)
    return results  # dict: path -> list of hashes
