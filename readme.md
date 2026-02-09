# MedMan

**MedMan** (Media Manager) is a smart deduplication tool for managing large collections of images and videos. It uses advanced hashing algorithms to identify both exact duplicates and visually similar files, helping you clean up your media library efficiently.

## Features

- **Dual Detection Methods**:
  - **Exact Matching**: Instant detection of identical files using SHA-256 hashing.
  - **Visual Similarity**: Uses Perceptual Hashing (pHash) for images and Frame Hashing for videos to find resized/transcoded duplicates.
- **Media Support**: Handles both Images (`.jpg`, `.png`, `.webp`, etc.) and Videos (`.mp4`, `.mkv`, etc.).
- **Interactive Review**: GUI-based comparison tool to manually review and select which duplicates to keep.
- **High Performance**: Multi-threaded processing for faster scanning of large directories.
- **Smart Clustering**: Groups similar files together for easy management.

## Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the script by pointing it to your media directory:

```bash
python main.py /path/to/your/media
```

### Options

| Flag | Description |
|------|-------------|
| `--interactive` | Launch GUI to manually review and resolve duplicates. |
| `--threshold [0.0-1.0]` | Set similarity threshold. Higher = stricter matching. (Default: 0.90 for auto, 0.80 for interactive) |
| `--image-only` | Scan only for image duplicates. |
| `--video-only` | Scan only for video duplicates. |
| `--video-frames [N]` | Number of frames to sample for video hashing (Default: 10). |

### Examples

**Automatic Scan (Safe Mode):**
Moves high-confidence duplicates to a `duplicates/` folder automatically.
```bash
python main.py ./photos
```

**Interactive Review (Recommended):**
Opens a window to let you choose better images/videos side-by-side.
```bash
python main.py ./photos --interactive
```

---

# TODO
1. Add watemark detection
2. ~~Video only/ Picture only scanning~~ ✅DONE
3. Better duplicate detection (better algorithm)