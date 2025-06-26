# --- CONFIGURABLE PARAMETERS ---
DEFAULT_VIDEO_FRAMES = 20 # Default frames to sample from each video for hashing
HIGH_THRESHOLD = 0.95 # for automatic deduplication
LOW_THRESHOLD = 0.85 # for interactive review
MAX_WORKERS = 8  # Max threads for all parallel processing
MAX_SHA_WORKERS = 16  # Max threads for SHA256 hashing
MAX_PHASH_WORKERS = 4  # Max threads for perceptual hashing
