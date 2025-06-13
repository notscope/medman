import os
import shutil

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