#!/usr/bin/env python3
"""
Lightweight watermark detector:
  • CPU‑only (OpenCV)
  • Template matching with CLAHE
  • Optional bounding box drawing

Usage examples:
---------------
Image:
    python watermark_detect_minimal.py image.jpg --templates watermarks/ --show
Video:
    python watermark_detect_minimal.py video.mp4 --templates watermarks/ --frames 5 --save matched.jpg
"""

import cv2
import numpy as np
import os
import argparse
from pathlib import Path

# ---------- Pre‑processing --------------------------------------------------

def preprocess(img):
    """Grayscale + CLAHE contrast boost."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)

# ---------- Template handling ----------------------------------------------

def load_templates(dir_path):
    """Return list of (name, preprocessed_template_img)."""
    tmpl = []
    for p in Path(dir_path).iterdir():
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            img = cv2.imread(str(p))
            if img is not None:
                tmpl.append((p.name, preprocess(img)))
    return tmpl

# ---------- Matching core ---------------------------------------------------

def match_once(search_img, template):
    """Single-scale template matching."""
    res = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return max_val, max_loc

def match_multiscale(search_img, templates, scales, threshold):
    """
    Try each template at all scales; return first match ≥ threshold.
    """
    for tpl_name, tpl in templates:
        h, w = tpl.shape[:2]
        for sc in scales:
            tpl_sc = cv2.resize(tpl, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
            if tpl_sc.size == 0 or tpl_sc.shape[0] > search_img.shape[0] or tpl_sc.shape[1] > search_img.shape[1]:
                continue
            score, loc = match_once(search_img, tpl_sc)
            if score >= threshold:
                match_info = {
                    "template": tpl_name,
                    "scale": sc,
                    "score": score,
                    "top_left": loc,
                    "size": tpl_sc.shape[::-1]  # (width, height)
                }
                return True, match_info
    return False, {}

def draw_match_box(img, match):
    """Draw rectangle and label on match."""
    x, y = match['top_left']
    w, h = match['size']
    annotated = img.copy()
    cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
    label = f"{match['template']} ({match['score']:.2f})"
    cv2.putText(annotated, label, (x, max(y - 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return annotated

# ---------- Image / video wrappers -----------------------------------------

def detect_in_image(path, templates, scales, thresh, show=False, save_path=None):
    img = cv2.imread(str(path))
    if img is None:
        return False, ["Image could not be read."]
    proc = preprocess(img)
    hit, match = match_multiscale(proc, templates, scales, thresh)
    if hit:
        annotated = draw_match_box(img, match)
        if show:
            cv2.imshow("Watermark Match", annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        if save_path:
            cv2.imwrite(save_path, annotated)
        return True, [f"{match['template']} | scale {match['scale']:.2f} | score {match['score']:.2f}"]
    return False, []

def detect_in_video(path, templates, scales, thresh, frames, show=False, save_path=None):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return False, ["Cannot open video."]
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, total // frames)

    for idx in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        proc = preprocess(frame)
        hit, match = match_multiscale(proc, templates, scales, thresh)
        if hit:
            annotated = draw_match_box(frame, match)
            if show:
                cv2.imshow("Watermark Match", annotated)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            if save_path:
                cv2.imwrite(save_path, annotated)
            cap.release()
            return True, [f"Frame {idx}: {match['template']} | scale {match['scale']:.2f} | score {match['score']:.2f}"]
    cap.release()
    return False, []

# ---------- CLI -------------------------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(description="Fast template watermark detector")
    ap.add_argument("path", help="Image or video file")
    ap.add_argument("--templates", required=True, help="Directory of watermark templates")
    ap.add_argument("-t", "--threshold", type=float, default=0.80, help="Match threshold (default: 0.80)")
    ap.add_argument("-s", "--scales", nargs="+", type=float, default=[1.0], help="Scales to try (e.g. 0.8 1.0 1.2)")
    ap.add_argument("-f", "--frames", type=int, default=5, help="Frames to sample for video (default: 5)")
    ap.add_argument("--show", action="store_true", help="Show annotated image/video frame")
    ap.add_argument("--save", help="Path to save annotated image")
    return ap.parse_args()

def main():
    args = parse_args()
    templates = load_templates(args.templates)
    if not templates:
        print("No valid templates found in", args.templates)
        return

    is_video = Path(args.path).suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"}
    if is_video:
        hit, info = detect_in_video(
            args.path, templates, args.scales, args.threshold,
            args.frames, show=args.show, save_path=args.save)
    else:
        hit, info = detect_in_image(
            args.path, templates, args.scales, args.threshold,
            show=args.show, save_path=args.save)

    if hit:
        print("✅  WATERMARK DETECTED")
        for line in info:
            print("   ", line)
    else:
        print("❌  No watermark detected.")

if __name__ == "__main__":
    main()
