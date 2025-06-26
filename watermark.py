### UNFINISHED CODE ###

from PIL import Image
import pytesseract
import cv2

def detect_watermark_image(path, min_text_len=5):
    img = Image.open(path).convert("RGB")
    text = pytesseract.image_to_string(img)

    # Strip whitespace and check if there's any readable text
    cleaned = text.strip()
    has_watermark = bool(cleaned)

    return has_watermark, cleaned

def detect_watermark_video(path, sample_frames=5, min_text_len=5):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return False

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, total_frames // sample_frames)

    found = False
    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        text = pytesseract.image_to_string(img)
        if any(len(word) >= min_text_len for word in text.split()):
            found = True
            break
    cap.release()
    return found

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detect watermark in an image or video")
    parser.add_argument("path", help="Path to image or video file")
    parser.add_argument("--frames", type=int, default=5, help="Frames to sample for video (default=5)")
    parser.add_argument("--min-text", type=int, default=5, help="Min length of detected text to flag watermark")
    args = parser.parse_args()

    path = args.path
    is_img = path.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))
    is_vid = path.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))

    if is_img:
        result, text = detect_watermark_image(path, min_text_len=args.min_text)
    elif is_vid:
        result = detect_watermark_video(path, sample_frames=args.frames, min_text_len=args.min_text)
    else:
        print("Unsupported file type.")
        exit(1)

    print(f"WATERMARK DETECTED" if result else "No watermark detected.")
    print(f"Detected text: {text}" if is_img else "No text extracted from video frames.")
