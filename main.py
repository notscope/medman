#!/usr/bin/env python3
import argparse
import os
import shutil
import hashlib
import warnings
from PIL import Image, ImageTk, UnidentifiedImageError
import imagehash
import tkinter as tk
from tkinter import ttk
import cv2

warnings.filterwarnings("ignore", category=UserWarning, module="PIL")

# --- CONFIGURABLE PARAMETERS ---
DEFAULT_VIDEO_FRAMES = 20
HIGH_THRESHOLD = 0.95 # for automatic deduplication
LOW_THRESHOLD = 0.85 # for interactive review

# --- UTILITY FUNCTIONS ---

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

def is_image(file):
    return file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))

def is_video(file):
    return file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))

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

def move_to_duplicates(path, base_duplicates_dir):
    try:
        rel_path = os.path.relpath(path, start=os.path.commonpath([path, base_duplicates_dir]))
    except Exception:
        rel_path = os.path.basename(path)
    new_path = os.path.join(base_duplicates_dir, rel_path)
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    shutil.move(path, new_path)
    return new_path

def print_action(label, src, dest):
    print(f"[{label}] Moved: {src} → {dest}")

def has_exif(path):
    try:
        img = Image.open(path)
        return hasattr(img, '_getexif') and img._getexif() is not None
    except:
        return False

# --- INTERACTIVE REVIEW GUI FOR IMAGES ---

def review_image_pair(path1, path2, meta1, meta2, similarity, on_decision):
    import os
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk

    def decision(choice):
        root.destroy()
        on_decision(choice)

    def format_metadata(meta):
        res, size = meta
        return f"{res[0]}x{res[1]}, {size//1024} KB"

    def resize_keep_aspect(img, max_width, max_height):
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return img.resize((max_width, max_height), Image.Resampling.LANCZOS)
        ratio = min(max_width / orig_w, max_height / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    root = tk.Tk()
    root.title("Image Duplicate Review")
    root.minsize(1200, 600)

    box_w, box_h = 420, 420
    img1 = Image.open(path1)
    img1_resized = resize_keep_aspect(img1, box_w, box_h)
    tk_img1 = ImageTk.PhotoImage(img1_resized)
    img2 = Image.open(path2)
    img2_resized = resize_keep_aspect(img2, box_w, box_h)
    tk_img2 = ImageTk.PhotoImage(img2_resized)

    # Use grid on root
    root.columnconfigure(0, weight=0)
    root.columnconfigure(1, weight=1)
    root.columnconfigure(2, weight=0)
    root.rowconfigure(0, weight=1)

    # Left frame
    left_frame = ttk.Frame(root)
    left_frame.grid(row=0, column=0, padx=5, pady=5)
    canvas1 = tk.Canvas(left_frame, width=box_w, height=box_h, bg='black')
    canvas1.pack()
    x1 = (box_w - img1_resized.width) // 2
    y1 = (box_h - img1_resized.height) // 2
    canvas1.create_image(x1, y1, image=tk_img1, anchor=tk.NW)
    canvas1.image = tk_img1
    ttk.Label(left_frame, text=os.path.basename(path1), wraplength=box_w, font=("monospace", 12)).pack(pady=2)

    # Center frame with three rows: top spacer, content, bottom spacer
    center_frame = ttk.Frame(root)
    center_frame.grid(row=0, column=1, sticky='nsew')
    center_frame.rowconfigure(0, weight=1)
    center_frame.rowconfigure(1, weight=0)
    center_frame.rowconfigure(2, weight=1)
    center_frame.columnconfigure(0, weight=1)

    content = ttk.Frame(center_frame)
    content.grid(row=1, column=0)

    # Metadata label
    label = ttk.Label(
        content,
        text=(
            f"Similarity: {similarity*100:.2f}%\n"
            f"Left: {format_metadata(meta1)}\n"
            f"Right: {format_metadata(meta2)}"
        ),
        font=("monospace", 15, "bold"),
        justify=tk.CENTER,
    )
    label.pack(pady=5)

    btn_frame = ttk.Frame(content)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)
    ttk.Button(btn_frame, text="A: Keep Left", command=lambda: decision('left')).pack(fill=tk.X, expand=True, pady=2)
    ttk.Button(btn_frame, text="D: Keep Right", command=lambda: decision('right')).pack(fill=tk.X, pady=2)
    ttk.Button(btn_frame, text="W: Keep Both", command=lambda: decision('both')).pack(fill=tk.X, pady=2)
    ttk.Button(btn_frame, text="S: Skip", command=lambda: decision('skip')).pack(fill=tk.X, pady=2)
    ttk.Button(btn_frame, text="Q: Quit", command=lambda: decision('quit')).pack(fill=tk.X, pady=2)

    # help_label = ttk.Label(content, text="A:Left  D:Right  W:Both  S:Skip  Q:Quit  H:Toggle Help", foreground='gray')
    # help_label.pack(pady=5)

    def bind_buttons():
        root.bind("a", lambda e: decision('left'))
        root.bind("d", lambda e: decision('right'))
        root.bind("w", lambda e: decision('both'))
        root.bind("s", lambda e: decision('skip'))
        root.bind("q", lambda e: decision('quit'))

    bind_buttons()

    # Right frame
    right_frame = ttk.Frame(root)
    right_frame.grid(row=0, column=2, padx=5, pady=5)
    canvas2 = tk.Canvas(right_frame, width=box_w, height=box_h, bg='black')
    canvas2.pack()
    x2 = (box_w - img2_resized.width) // 2
    y2 = (box_h - img2_resized.height) // 2
    canvas2.create_image(x2, y2, image=tk_img2, anchor=tk.NW)
    canvas2.image = tk_img2
    ttk.Label(right_frame, text=os.path.basename(path2), wraplength=box_w, font=("monospace", 12)).pack(pady=2)

    root.mainloop()


# --- INTERACTIVE REVIEW GUI FOR VIDEOS ---

def review_video_pair(path1, path2, meta1, meta2, similarity, on_decision):
    import os
    import tkinter as tk
    from tkinter import ttk
    from PIL import Image, ImageTk
    import cv2

    class VideoReviewApp:
        def __init__(self, master):
            self.master = master
            self.decision_made = False
            self.video_path1 = path1
            self.video_path2 = path2
            self.meta1 = meta1
            self.meta2 = meta2
            self.similarity = similarity
            self.on_decision = on_decision

            self.build_ui()
            self.bind_keys()
            self.play_videos()

        def build_ui(self):
            # Configure grid layout
            self.master.columnconfigure(0, weight=0)
            self.master.columnconfigure(1, weight=1)
            self.master.columnconfigure(2, weight=0)
            self.master.rowconfigure(0, weight=1)

            # Left frame with video and label
            left_frame = ttk.Frame(self.master)
            left_frame.grid(row=0, column=0, padx=5, pady=5)
            self.canvas1 = tk.Canvas(left_frame, width=640, height=360, bg='black')
            self.canvas1.pack()
            ttk.Label(left_frame, text=os.path.basename(self.video_path1), wraplength=640).pack(pady=2)

            # Right frame with video and label
            right_frame = ttk.Frame(self.master)
            right_frame.grid(row=0, column=2, padx=5, pady=5)
            self.canvas2 = tk.Canvas(right_frame, width=640, height=360, bg='black')
            self.canvas2.pack()
            ttk.Label(right_frame, text=os.path.basename(self.video_path2), wraplength=640).pack(pady=2)

            # Center frame (will hold 3 rows: spacer, controls, spacer)
            center_frame = ttk.Frame(self.master)
            center_frame.grid(row=0, column=1, sticky='nsew')
            center_frame.rowconfigure(0, weight=1)
            center_frame.rowconfigure(1, weight=0)
            center_frame.rowconfigure(2, weight=1)
            center_frame.columnconfigure(0, weight=1)

            # Actual content frame (vertically centered)
            content = ttk.Frame(center_frame)
            content.grid(row=1, column=0)
            label_similarity = f"Similarity: {self.similarity*100:.2f}%\n"
            label_text = (
                f"Left: {self.format_meta(self.meta1)}\n"
                f"Right: {self.format_meta(self.meta2)}"
            )
            ttk.Label(content, text=label_similarity, font=("monospace", 20, "bold"), justify=tk.CENTER).pack()
            ttk.Label(content, text=label_text, justify=tk.CENTER).pack(pady=5)

            btn_frame = ttk.Frame(content)
            btn_frame.pack(fill=tk.X, padx=10, pady=5)
            ttk.Button(btn_frame, text="A: Keep Left", command=lambda: self.decision('left')).pack(fill=tk.X, pady=2)
            ttk.Button(btn_frame, text="D: Keep Right", command=lambda: self.decision('right')).pack(fill=tk.X, pady=2)
            ttk.Button(btn_frame, text="W: Keep Both", command=lambda: self.decision('both')).pack(fill=tk.X, pady=2)
            ttk.Button(btn_frame, text="S: Skip", command=lambda: self.decision('skip')).pack(fill=tk.X, pady=2)
            ttk.Button(btn_frame, text="Q: Quit", command=lambda: self.decision('quit')).pack(fill=tk.X, pady=2)
            ttk.Button(btn_frame, text="P: Replay", command=self.replay).pack(fill=tk.X, pady=2)

        def bind_keys(self):
            self.master.bind("a", lambda e: self.decision('left'))
            self.master.bind("d", lambda e: self.decision('right'))
            self.master.bind("w", lambda e: self.decision('both'))
            self.master.bind("s", lambda e: self.decision('skip'))
            self.master.bind("q", lambda e: self.decision('quit'))
            self.master.bind("p", lambda e: self.replay())

        def format_meta(self, m):
            res, dur, size = m
            return f"{res[0]}x{res[1]}, {dur:.1f}s, {size//1024} KB"

        def play_videos(self):
            self.cap_left = cv2.VideoCapture(self.video_path1)
            self.cap_right = cv2.VideoCapture(self.video_path2)
            self.play_frame()

        def play_frame(self):
            if self.decision_made:
                if hasattr(self, 'cap_left'):
                    self.cap_left.release()
                if hasattr(self, 'cap_right'):
                    self.cap_right.release()
                return

            ret1, frame1 = self.cap_left.read() if hasattr(self, 'cap_left') else (False, None)
            ret2, frame2 = self.cap_right.read() if hasattr(self, 'cap_right') else (False, None)

            if ret1:
                self._display_on_canvas(frame1, self.canvas1)
            if ret2:
                self._display_on_canvas(frame2, self.canvas2)

            if ret1 or ret2:
                self.master.after(33, self.play_frame)
            else:
                if hasattr(self, 'cap_left'):
                    self.cap_left.release()
                if hasattr(self, 'cap_right'):
                    self.cap_right.release()

        def _display_on_canvas(self, frame, canvas):
            h_box, w_box = 360, 640
            h, w = frame.shape[:2]
            if w == 0 or h == 0:
                return
            ratio = min(w_box / w, h_box / h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            resized = cv2.resize(frame, (new_w, new_h))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(Image.fromarray(rgb))
            x_offset = (w_box - new_w) // 2
            y_offset = (h_box - new_h) // 2
            canvas.delete("all")
            canvas.create_image(x_offset, y_offset, image=img, anchor=tk.NW)
            canvas.image = img

        def replay(self):
            if hasattr(self, 'cap_left'):
                self.cap_left.release()
            if hasattr(self, 'cap_right'):
                self.cap_right.release()
            self.play_videos()

        def decision(self, choice):
            self.decision_made = True
            if hasattr(self, 'cap_left'):
                self.cap_left.release()
            if hasattr(self, 'cap_right'):
                self.cap_right.release()
            self.master.destroy()
            self.on_decision(choice)

    root = tk.Tk()
    root.minsize(1700, 450)
    root.title("Video Duplicate Review")
    app = VideoReviewApp(root)
    root.mainloop()

# --- CLUSTERING UTILITIES ---

class UnionFind:
    def __init__(self):
        self.parent = {}
    def find(self, x):
        if self.parent.setdefault(x, x) != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[ry] = rx

def cluster_images(image_paths, threshold):
    # 1) SHA groups
    sha_map = {}
    for p in image_paths:
        sha = hash_file_sha256(p)
        if sha is None: continue
        sha_map.setdefault(sha, []).append(p)
    uf = UnionFind()
    # Union exact duplicates
    for paths in sha_map.values():
        if len(paths) > 1:
            first = paths[0]
            for other in paths[1:]:
                uf.union(first, other)
    # 2) Representatives for perceptual hash
    reps = []
    phashes = {}
    for sha, paths in sha_map.items():
        rep = paths[0]
        h = hash_image_phash(rep)
        if h is None: continue
        reps.append(rep)
        phashes[rep] = h
    # 3) Compare perceptual hashes
    n = len(reps)
    for i in range(n):
        for j in range(i+1, n):
            p1, p2 = reps[i], reps[j]
            h1, h2 = phashes[p1], phashes[p2]
            sim = 1 - (h1 - h2) / 64.0
            if sim >= threshold:
                uf.union(p1, p2)
    # 4) Build clusters
    clusters = {}
    for sha, paths in sha_map.items():
        rep = paths[0]
        if rep in uf.parent:
            root = uf.find(rep)
            clusters.setdefault(root, []).extend(paths)
    return [group for group in clusters.values() if len(group) > 1]

def cluster_videos(video_paths, threshold, sample_count):
    # 1) SHA groups
    sha_map = {}
    for p in video_paths:
        sha = hash_file_sha256(p)
        if sha is None: continue
        sha_map.setdefault(sha, []).append(p)
    uf = UnionFind()
    for paths in sha_map.values():
        if len(paths) > 1:
            first = paths[0]
            for other in paths[1:]:
                uf.union(first, other)
    # 2) Representatives for perceptual-video hash
    reps = []
    vhashes = {}
    for sha, paths in sha_map.items():
        rep = paths[0]
        hlist = hash_video_frames(rep, sample_count)
        if not hlist: continue
        reps.append(rep)
        vhashes[rep] = hlist
    # 3) Compare
    n = len(reps)
    for i in range(n):
        for j in range(i+1, n):
            p1, p2 = reps[i], reps[j]
            sim = compare_video_hashes(vhashes[p1], vhashes[p2])
            if sim >= threshold:
                uf.union(p1, p2)
    # 4) Build clusters
    clusters = {}
    for sha, paths in sha_map.items():
        rep = paths[0]
        if rep in uf.parent:
            root = uf.find(rep)
            clusters.setdefault(root, []).extend(paths)
    return [group for group in clusters.values() if len(group) > 1]

# --- QUALITY SCORING ---

def score_image(path):
    res, size = get_image_metadata(path)
    ex = 1000 if has_exif(path) else 0
    return res[0] * res[1] + size + ex

def score_video(path):
    res, dur, size = get_video_metadata(path)
    return res[0] * res[1] + dur * 10 + size

# --- HANDLERS FOR CLUSTERS ---

def handle_image_cluster(cluster, interactive, duplicates_dir):
    scored = sorted([(score_image(p), p) for p in cluster], reverse=True)
    best = [scored[0][1]]  # mutable container holding current best
    others = [p for _, p in scored[1:]]
    for other in others:
        if not os.path.exists(best[0]) or not os.path.exists(other):
            continue
        # Check exact SHA first
        sha_best = hash_file_sha256(best[0])
        sha_other = hash_file_sha256(other)
        if sha_best is not None and sha_best == sha_other:
            # exact duplicate → auto-move other without GUI
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("SHA", other, dest)
            continue

        if interactive:
            # compute metadata and perceptual similarity
            meta_best = get_image_metadata(best[0])
            meta_other = get_image_metadata(other)
            h1 = hash_image_phash(best[0])
            h2 = hash_image_phash(other)
            if h1 is None or h2 is None:
                sim = 0.0
            else:
                sim = 1 - (h1 - h2) / 64.0
            # define handler to possibly update best
            def make_handler(b_list, o):
                def handler(decision):
                    if decision == 'left':
                        # keep best: remove other
                        dest = move_to_duplicates(o, duplicates_dir)
                        print_action("PHASH", o, dest)
                    elif decision == 'right':
                        # keep other: remove best, update best
                        dest = move_to_duplicates(b_list[0], duplicates_dir)
                        print_action("PHASH", b_list[0], dest)
                        b_list[0] = o
                    elif decision in ('both', 'skip'):
                        pass
                    elif decision == 'quit':
                        exit()
                return handler
            handler = make_handler(best, other)
            review_image_pair(best[0], other, meta_best, meta_other, sim, handler)
        else:
            # automatic: move other
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("AUTO_IMG", other, dest)


def handle_video_cluster(cluster, interactive, duplicates_dir, sample_count):
    scored = sorted([(score_video(p), p) for p in cluster], reverse=True)
    best = [scored[0][1]]
    others = [p for _, p in scored[1:]]
    for other in others:
        if not os.path.exists(best[0]) or not os.path.exists(other):
            continue
        # Exact-SHA check
        sha_best = hash_file_sha256(best[0])
        sha_other = hash_file_sha256(other)
        if sha_best is not None and sha_best == sha_other:
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("SHA", other, dest)
            continue

        if interactive:
            meta_best = get_video_metadata(best[0])
            meta_other = get_video_metadata(other)
            # perceptual similarity
            vhash_best = hash_video_frames(best[0], sample_count)
            vhash_other = hash_video_frames(other, sample_count)
            sim = compare_video_hashes(vhash_best, vhash_other)
            def make_handler(b_list, o):
                def handler(decision):
                    if decision == 'left':
                        dest = move_to_duplicates(o, duplicates_dir)
                        print_action("VIDHASH", o, dest)
                    elif decision == 'right':
                        dest = move_to_duplicates(b_list[0], duplicates_dir)
                        print_action("VIDHASH", b_list[0], dest)
                        b_list[0] = o
                    elif decision in ('both', 'skip'):
                        pass
                    elif decision == 'quit':
                        exit()
                return handler
            handler = make_handler(best, other)
            review_video_pair(best[0], other, meta_best, meta_other, sim, handler)
        else:
            dest = move_to_duplicates(other, duplicates_dir)
            print_action("AUTO_VID", other, dest)


# --- MAIN PROCESSING LOGIC ---

def main():
    parser = argparse.ArgumentParser(description="Smart deduplicate images/videos")
    parser.add_argument("directory", help="Directory to scan for duplicates")
    parser.add_argument("--interactive", action="store_true",
                        help="Interactive review after clustering duplicates")
    parser.add_argument("--threshold", type=float, help="Similarity threshold (0.0–1.0)")
    parser.add_argument("--video-frames", type=int, default=DEFAULT_VIDEO_FRAMES,
                        help="Frames to sample for video hashing")
    args = parser.parse_args()

    # Validate threshold
    if args.threshold is not None:
        if not (0.0 <= args.threshold <= 1.0):
            parser.error(f"--threshold must be between 0.0 and 1.0, got {args.threshold}")
        threshold = args.threshold
    else:
        threshold = LOW_THRESHOLD if args.interactive else HIGH_THRESHOLD
    print(f"[INFO] Using similarity threshold = {threshold:.2f}")

    sample_count = args.video_frames
    base_dir = os.path.abspath(args.directory)
    duplicates_dir = os.path.join(base_dir, "duplicates")
    os.makedirs(duplicates_dir, exist_ok=True)

    # Collect all files first
    image_paths = []
    video_paths = []
    for root_dir, _, files in os.walk(base_dir):
        if duplicates_dir in root_dir:
            continue
        for f in files:
            p = os.path.join(root_dir, f)
            if not os.path.isfile(p):
                continue
            if is_image(f):
                image_paths.append(p)
            elif is_video(f):
                video_paths.append(p)

    # Cluster images
    print("[INFO] Clustering images...")
    img_clusters = cluster_images(image_paths, threshold)
    print(f"[INFO] Found {len(img_clusters)} image duplicate cluster(s).")
    for cluster in img_clusters:
        handle_image_cluster(cluster, args.interactive, duplicates_dir)

    # Cluster videos
    print("[INFO] Clustering videos...")
    vid_clusters = cluster_videos(video_paths, threshold, sample_count)
    print(f"[INFO] Found {len(vid_clusters)} video duplicate cluster(s).")
    for cluster in vid_clusters:
        handle_video_cluster(cluster, args.interactive, duplicates_dir, sample_count)

if __name__ == "__main__":
    main()