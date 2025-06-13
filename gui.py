# --- INTERACTIVE REVIEW GUI FOR IMAGES ---
import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2

def review_image_pair(path1, path2, meta1, meta2, similarity, on_decision):
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
    label_similarity_text = f"Similarity: {similarity*100:.2f}%\n"
    label_text = ttk.Label(
        content,
        text=(
            f"Left: {format_metadata(meta1)}\n"
            f"Right: {format_metadata(meta2)}"
        ),
        justify=tk.CENTER,
    )

    label_similarity = ttk.Label(content, text=label_similarity_text, font=("monospace", 20, "bold"), justify=tk.CENTER)
    label_similarity.pack()
    label_text.pack(pady=5)

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
            ttk.Button(btn_frame, text="P: Replay", command=self.replay).pack(fill=tk.X, pady=2)
            ttk.Button(btn_frame, text="Q: Quit", command=lambda: self.decision('quit')).pack(fill=tk.X, pady=2)

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
