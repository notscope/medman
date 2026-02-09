import os

# --- CONFIGURABLE PARAMETERS ---
DEFAULT_VIDEO_FRAMES = 10 # Default frames to sample from each video for hashing
HIGH_THRESHOLD = 0.95 # for automatic deduplication
LOW_THRESHOLD = 0.89 # for interactive review

CPU_COUNT = os.cpu_count() or 4
MAX_WORKERS = CPU_COUNT * 2  # Max threads for general parallel processing
MAX_SHA_WORKERS = CPU_COUNT * 4  # Max threads for SHA256 hashing (I/O bound)
MAX_PHASH_WORKERS = CPU_COUNT     # Max processes for perceptual hashing (CPU bound)
