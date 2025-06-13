from metadata import get_image_metadata, get_video_metadata, has_exif

# --- QUALITY SCORING ---

def score_image(path):
    res, size = get_image_metadata(path)
    ex = 1000 if has_exif(path) else 0
    return res[0] * res[1] + size + ex

def score_video(path):
    res, dur, size = get_video_metadata(path)
    return res[0] * res[1] + dur * 10 + size