#!/usr/bin/env python3
import argparse
import os
import warnings
from clustering import cluster_images, cluster_videos, handle_image_cluster, handle_video_cluster
from config import DEFAULT_VIDEO_FRAMES, LOW_THRESHOLD, HIGH_THRESHOLD

warnings.filterwarnings("ignore", category=UserWarning, module="PIL")

# --- UTILITY FUNCTIONS ---

def is_image(file):
    return file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp'))

def is_video(file):
    return file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))

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
    for idx, cluster in enumerate(img_clusters, start=1):
        handle_image_cluster(cluster, args.interactive, duplicates_dir, idx, len(img_clusters))

    # Cluster videos
    print("[INFO] Clustering videos...")
    vid_clusters = cluster_videos(video_paths, threshold, sample_count)
    print(f"[INFO] Found {len(vid_clusters)} video duplicate cluster(s).")
    for idx, cluster in enumerate(vid_clusters, start=1):
        handle_video_cluster(cluster, args.interactive, duplicates_dir, sample_count, idx, len(vid_clusters))

    print("[INFO] Processing complete.")

if __name__ == "__main__":
    main()