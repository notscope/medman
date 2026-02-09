#!/usr/bin/env python3
"""
MedMan Web UI - FastAPI + Jinja2 + HTMX
"""
import os
import threading
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import Response

from clustering import cluster_images, cluster_videos
from hashing import hash_file_sha256, hash_image_phash, hash_video_frames, compare_video_hashes
from metadata import get_image_metadata, get_video_metadata
from move_files import move_to_duplicates
from scoring import score_image, score_video
from config import DEFAULT_VIDEO_FRAMES, LOW_THRESHOLD, MAX_SHA_WORKERS, MAX_PHASH_WORKERS

app = FastAPI(title="MedMan Web UI")

# --- Configuration ---
# Generate secret key or use env var
SECRET_KEY = os.environ.get("MEDMAN_SECRET_KEY", os.urandom(24).hex())
# Get allowed users from env var (format: "user:pass,admin:secret")
DEFAULT_USERS = "admin:medman"
ALLOWED_USERS = {}
for user_pass in os.environ.get("MEDMAN_USERS", DEFAULT_USERS).split(","):
    if ":" in user_pass:
        u, p = user_pass.split(":", 1)
        ALLOWED_USERS[u.strip()] = p.strip()


# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- In-memory State ---
class ScanState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.directory: Optional[str] = None
        self.status: str = "idle"  # idle, scanning, ready, done
        self.progress: str = ""
        self.clusters: list = []
        self.current_index: int = 0
        self.duplicates_dir: Optional[str] = None
        self.threshold: float = 0.89
        self.progress_percent: int = 0
        self.progress_label: str = ""
        self.history: list = [] # List of (choice, source_path, dest_path, cluster_index, cluster_files_copy)

state = ScanState()

# --- Utility Functions ---
def is_image(file: str) -> bool:
    return file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))

def is_video(file: str) -> bool:
    return file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))

def get_truncated_paths(path1: str, path2: str) -> tuple:
    """Get truncated paths showing only the diverging parts."""
    parts1 = path1.split(os.sep)
    parts2 = path2.split(os.sep)
    
    # Find common prefix length
    common_len = 0
    for i in range(min(len(parts1), len(parts2))):
        if parts1[i] == parts2[i]:
            common_len = i + 1
        else:
            break
    
    # Return paths from where they start to differ
    # Include one level before the difference for context
    start = max(0, common_len - 1)
    truncated1 = os.sep.join(parts1[start:])
    truncated2 = os.sep.join(parts2[start:])
    
    return truncated1, truncated2

def run_scan(directory: str, threshold: float):
    """Background scan task."""
    global state
    state.status = "scanning"
    state.progress = "Collecting files..."

    base_dir = os.path.abspath(directory)
    state.duplicates_dir = os.path.join(base_dir, "duplicates")
    os.makedirs(state.duplicates_dir, exist_ok=True)

    image_paths = []
    video_paths = []
    for root_dir, _, files in os.walk(base_dir):
        if state.duplicates_dir in root_dir:
            continue
        for f in files:
            p = os.path.join(root_dir, f)
            if not os.path.isfile(p):
                continue
            if is_image(f):
                image_paths.append(p)
            elif is_video(f):
                video_paths.append(p)

    state.progress = f"Found {len(image_paths)} images, {len(video_paths)} videos. Clustering images..."

    # Clustering progress callback
    def progress_cb(label, curr, tot):
        state.progress_label = label
        state.progress_percent = int((curr / tot) * 100) if tot > 0 else 0
        state.progress = f"{label} ({state.progress_percent}%)"

    try:
        # Cluster Images
        state.progress = "Clustering images..."
        img_clusters = cluster_images(image_paths, threshold, MAX_SHA_WORKERS, MAX_PHASH_WORKERS, progress_callback=progress_cb)
        state.progress = f"Found {len(img_clusters)} image clusters. Clustering videos..."
        
        # Cluster Videos
        state.progress = "Clustering videos..."
        vid_clusters = cluster_videos(video_paths, threshold, DEFAULT_VIDEO_FRAMES, MAX_SHA_WORKERS, MAX_PHASH_WORKERS, progress_callback=progress_cb)
        state.progress = f"Found {len(vid_clusters)} video clusters."
    except Exception as e:
        state.status = "error"
        state.progress = f"Error during clustering: {e}"
        return

    # Prepare clusters for review
    all_clusters = []
    for cluster in img_clusters:
        scored = sorted([(score_image(p), p) for p in cluster], reverse=True)
        all_clusters.append({"type": "image", "files": [p for _, p in scored]})
    for cluster in vid_clusters:
        scored = sorted([(score_video(p), p) for p in cluster], reverse=True)
        all_clusters.append({"type": "video", "files": [p for _, p in scored]})

    state.clusters = all_clusters
    state.current_index = 0
    state.status = "ready" if all_clusters else "done"
    state.progress = f"Scan complete. {len(all_clusters)} cluster(s) to review."

# --- Authentication Dependency ---
async def get_current_user(request: Request):
    user = request.session.get("user")
    if not user:
        # Check if request is for login page or static files
        if request.url.path in ["/login", "/logout"] or request.url.path.startswith("/static"):
            return None
        # Redirect to login for other pages
        raise HTTPException(status_code=303, detail="Not authenticated") 
    return user

# --- Routes ---

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Skip auth for static files and login page
    if request.url.path in ["/login", "/logout"] or request.url.path.startswith("/static"):
        return await call_next(request)
    
    user = request.session.get("user")
    if not user:
        return RedirectResponse("/login", status_code=303)
    
    return await call_next(request)

# Add Session Middleware (Must be added last to wrap Auth middleware)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in ALLOWED_USERS and ALLOWED_USERS[username] == password:
        request.session["user"] = username
        return RedirectResponse("/", status_code=303)
    
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "state": state, "user": request.session.get("user")})

@app.post("/scan", response_class=HTMLResponse)
async def start_scan(request: Request, directory: str = Form(...), threshold: float = Form(0.89)):
    if not os.path.isdir(directory):
        return templates.TemplateResponse("partials/error.html", {"request": request, "message": f"Invalid directory: {directory}"})

    state.reset()
    state.directory = directory
    state.threshold = threshold
    state.status = "scanning"
    state.progress = "Starting scan..."

    # Run scan in background thread
    thread = threading.Thread(target=run_scan, args=(directory, threshold), daemon=True)
    thread.start()

    return templates.TemplateResponse("partials/progress.html", {"request": request, "state": state})

@app.get("/scan/status", response_class=HTMLResponse)
async def scan_status(request: Request):
    return templates.TemplateResponse("partials/progress.html", {"request": request, "state": state})

@app.get("/review", response_class=HTMLResponse)
async def review(request: Request):
    if state.status == "done" or state.current_index >= len(state.clusters):
        return templates.TemplateResponse("partials/done.html", {"request": request})

    cluster = state.clusters[state.current_index]
    files = cluster["files"]
    if len(files) < 2:
        state.current_index += 1
        return RedirectResponse("/review", status_code=303)

    left_path = files[0]
    right_path = files[1]
    cluster_type = cluster["type"]

    # Get metadata
    if cluster_type == "image":
        meta_left = get_image_metadata(left_path)
        meta_right = get_image_metadata(right_path)
        h1 = hash_image_phash(left_path)
        h2 = hash_image_phash(right_path)
        if h1 and h2:
            similarity = 1 - (h1 - h2) / 64.0
        else:
            similarity = 0.0
    else:
        meta_left = get_video_metadata(left_path)
        meta_right = get_video_metadata(right_path)
        h1 = hash_video_frames(left_path, DEFAULT_VIDEO_FRAMES)
        h2 = hash_video_frames(right_path, DEFAULT_VIDEO_FRAMES)
        similarity = compare_video_hashes(h1, h2)

    # Enforce threshold: if similarity is too low, skip this "other" file
    if similarity < state.threshold:
        files.pop(1) # Remove the divergent file from the cluster
        return RedirectResponse("/review", status_code=303)

    # Get truncated paths for display
    left_truncated, right_truncated = get_truncated_paths(left_path, right_path)

    return templates.TemplateResponse("review.html", {
        "request": request,
        "left_path": left_path,
        "right_path": right_path,
        "left_name": os.path.basename(left_path),
        "right_name": os.path.basename(right_path),
        "left_truncated": left_truncated,
        "right_truncated": right_truncated,
        "meta_left": meta_left,
        "meta_right": meta_right,
        "similarity": similarity,
        "cluster_type": cluster_type,
        "cluster_index": state.current_index + 1,
        "cluster_total": len(state.clusters),
    })

@app.post("/decision/{choice}", response_class=HTMLResponse)
async def handle_decision(request: Request, choice: str):
    if state.current_index >= len(state.clusters):
        return RedirectResponse("/review", status_code=303)

    cluster = state.clusters[state.current_index]
    files = cluster["files"]
    left_path = files[0]
    right_path = files[1]

    import shutil
    action = None
    if choice == "left":
        # Keep left: move right to duplicates
        dest = move_to_duplicates(right_path, state.duplicates_dir)
        action = ("left", right_path, dest, state.current_index, list(files))
        files.pop(1)
    elif choice == "right":
        # Keep right: move left to duplicates, right becomes new "best"
        dest = move_to_duplicates(left_path, state.duplicates_dir)
        action = ("right", left_path, dest, state.current_index, list(files))
        files.pop(0)
    elif choice == "skip":
        # Skip this "other" file for now
        action = ("skip", None, None, state.current_index, list(files))
        files.pop(1)

    if action:
        state.history.append(action)
        if len(state.history) > 10:
            state.history.pop(0)

    # If cluster has only 1 file left, it's done; move to next cluster
    if len(files) < 2:
        state.current_index += 1

    return RedirectResponse("/review", status_code=303)

@app.post("/review/undo", response_class=HTMLResponse)
async def undo_decision(request: Request):
    if not state.history:
        return RedirectResponse("/review", status_code=303)

    import shutil
    choice, moved_path, dest_path, prev_index, prev_files = state.history.pop()
    
    # Revert state index/files
    state.current_index = prev_index
    state.clusters[state.current_index]["files"] = prev_files
    
    # If choice involved moving a file, move it back
    if choice in ["left", "right"] and dest_path and os.path.exists(dest_path):
        try:
            # Ensure parent directory exists (it should, but just in case)
            os.makedirs(os.path.dirname(moved_path), exist_ok=True)
            shutil.move(dest_path, moved_path)
        except Exception as e:
            print(f"Error undoing move: {e}")

    return RedirectResponse("/review", status_code=303)

@app.get("/api/browse", response_class=HTMLResponse)
async def browse_files(request: Request, path: str = ""):
    current_path = path if path else os.path.expanduser("~")
    # Normalize path to fix double slashes (e.g. //home -> /home)
    current_path = os.path.normpath(current_path)
    if current_path.startswith("//"):
        current_path = current_path[1:]

    if not os.path.isdir(current_path):
        current_path = os.path.expanduser("~")

    try:
        # List directories only
        items = []
        with os.scandir(current_path) as it:
            for entry in it:
                if entry.is_dir() and not entry.name.startswith('.'):
                    items.append(entry.name)
        
        items.sort(key=str.lower)
        
        parent_path = os.path.dirname(current_path)
        
        # Generate breadcrumbs
        breadcrumbs = []
        parts = current_path.strip(os.sep).split(os.sep)
        acc_path = ""
        if current_path.startswith(os.sep):
            acc_path = os.sep
            breadcrumbs.append({"name": "root", "path": acc_path})
        
        for part in parts:
            if not part: continue
            acc_path = os.path.join(acc_path, part)
            breadcrumbs.append({"name": part, "path": acc_path})

        return templates.TemplateResponse("partials/file_browser_list.html", {
            "request": request,
            "current_path": current_path,
            "parent_path": parent_path,
            "items": items,
            "breadcrumbs": breadcrumbs
        })
    except PermissionError:
        return templates.TemplateResponse("partials/error.html", {
            "request": request,
            "message": f"Permission denied: {current_path}"
        })



@app.get("/media/{path:path}")
async def serve_media(path: str):
    # Decode and serve local file
    full_path = "/" + path
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
