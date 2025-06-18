import os
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2

class ReviewWindow:
    def __init__(self, master, path1, path2, meta1, meta2, similarity, on_decision, video=False, cluster_index=None, cluster_total=None):
        """
        master: a tk.Tk() or tk.Toplevel() instance
        path1, path2: file paths (images or videos)
        meta1, meta2: metadata tuples; for images: ((w,h), size), for videos: ((w,h), duration, size)
        similarity: float in [0,1]
        on_decision: callback function accepting one argument: choice string in {'left','right','both','skip','quit'}
        video: bool, True=video mode, False=image mode
        cluster_index: int, index of this pair in the cluster (if applicable)
        cluster_total: int, total pairs in the cluster (if applicable)
        """
        self.master = master
        self.item_path1 = path1
        self.item_path2 = path2
        self.meta1 = meta1
        self.meta2 = meta2
        self.similarity = similarity
        self.on_decision = on_decision
        self.video = video
        self.cluster_index = cluster_index
        self.cluster_total = cluster_total
        self.decision_made = False

        # Define box sizes
        if self.video:
            # Video canvas box
            self.box_w, self.box_h = 640, 360
        else:
            # Image display box
            self.box_w, self.box_h = 420, 420
        # Preload images if image mode
        if not self.video:
            # Load and resize images keeping aspect
            try:
                img1 = Image.open(self.item_path1)
                img2 = Image.open(self.item_path2)
            except Exception as e:
                # If loading fails, create blank placeholders
                img1 = Image.new('RGB', (self.box_w, self.box_h), 'gray')
                img2 = Image.new('RGB', (self.box_w, self.box_h), 'gray')
                print(f"Warning: failed to open images: {e}")
            self.tk_img1 = self._resize_keep_aspect_tk(img1, self.box_w, self.box_h)
            self.tk_img2 = self._resize_keep_aspect_tk(img2, self.box_w, self.box_h)

        # Build UI
        self.master.title("Video Duplicate Review" if self.video else "Image Duplicate Review")
        
        # Set a minimum size
        if self.video:
            # wide layout
            self.master.minsize(self.box_w*2 + 300, self.box_h + 100)
        else:
            self.master.minsize(self.box_w*2 + 300, self.box_h + 100)
        self.build_ui()
        self.bind_keys()
        if self.video:
            # after UI is built, start video playback
            self.play_videos()

    def build_ui(self):
        # Use grid on root: 3 columns (left, center, right), single row
        self.master.columnconfigure(0, weight=0)
        self.master.columnconfigure(1, weight=1)
        self.master.columnconfigure(2, weight=0)
        self.master.rowconfigure(0, weight=1)

        # LEFT FRAME
        left_frame = ttk.Frame(self.master)
        left_frame.grid(row=0, column=0, padx=5, pady=5)
        # Canvas for image or video
        self.canvas1 = tk.Canvas(left_frame, width=self.box_w, height=self.box_h, bg='black')
        self.canvas1.pack()
        # If image: place static image
        if not self.video:
            x1 = (self.box_w - self.tk_img1.width()) // 2
            y1 = (self.box_h - self.tk_img1.height()) // 2
            self.canvas1.create_image(x1, y1, image=self.tk_img1, anchor=tk.NW)
            self.canvas1.image = self.tk_img1
        # Filename label
        ttk.Label(left_frame, text=os.path.basename(self.item_path1), wraplength=self.box_w, font=("monospace", 12)).pack(pady=2)

        # RIGHT FRAME
        right_frame = ttk.Frame(self.master)
        right_frame.grid(row=0, column=2, padx=5, pady=5)
        self.canvas2 = tk.Canvas(right_frame, width=self.box_w, height=self.box_h, bg='black')
        self.canvas2.pack()
        if not self.video:
            x2 = (self.box_w - self.tk_img2.width()) // 2
            y2 = (self.box_h - self.tk_img2.height()) // 2
            self.canvas2.create_image(x2, y2, image=self.tk_img2, anchor=tk.NW)
            self.canvas2.image = self.tk_img2
        ttk.Label(right_frame, text=os.path.basename(self.item_path2), wraplength=self.box_w, font=("monospace", 12)).pack(pady=2)

        # CENTER FRAME: three rows to center content vertically
        center_frame = ttk.Frame(self.master)
        center_frame.grid(row=0, column=1, sticky='nsew')
        center_frame.rowconfigure(0, weight=1)
        center_frame.rowconfigure(1, weight=0)
        center_frame.rowconfigure(2, weight=1)
        center_frame.columnconfigure(0, weight=1)

        # Content frame in middle row
        content = ttk.Frame(center_frame)
        content.grid(row=1, column=0)

        # Cluster, similarity and metadata label
        # For video, show similarity first; metadata lines below
        if self.cluster_index is not None and self.cluster_total is not None:
            cluster_info = f"Cluster {self.cluster_index} of {self.cluster_total}\n"
            ttk.Label(content, text=cluster_info, justify=tk.CENTER).pack()

        sim_text = f"Similarity: {self.similarity * 100:.2f}%\n"
        if self.video:
            meta_text = f"Left: {self.format_meta(self.meta1)}\nRight: {self.format_meta(self.meta2)}"
        else:
            meta_text = f"Left: {self.format_meta(self.meta1)}\nRight: {self.format_meta(self.meta2)}"
        ttk.Label(content, text=sim_text, font=("monospace", 16, "bold"), justify=tk.CENTER).pack()
        ttk.Label(content, text=meta_text, justify=tk.CENTER).pack(pady=5)

        # Buttons stacked vertically, full width of content
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="A: Keep Left", command=lambda: self.decision('left')).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="D: Keep Right", command=lambda: self.decision('right')).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="W: Keep Both", command=lambda: self.decision('both')).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="S: Skip", command=lambda: self.decision('skip')).pack(fill=tk.X, pady=2)
        if self.video:
            ttk.Button(btn_frame, text="R: Replay", command=self.replay).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Q: Quit", command=lambda: self.decision('quit')).pack(fill=tk.X, pady=2)

    def bind_keys(self):
        self.master.bind("a", lambda e: self.decision('left'))
        self.master.bind("d", lambda e: self.decision('right'))
        self.master.bind("w", lambda e: self.decision('both'))
        self.master.bind("s", lambda e: self.decision('skip'))
        self.master.bind("q", lambda e: self.decision('quit'))
        if self.video:
            self.master.bind("r", lambda e: self.replay())
        # self.master.bind("h", lambda e: self.toggle_help())

    def format_meta(self, m):
        # For images: m = ((w,h), size)
        # For videos: m = ((w,h), duration, size)
        if self.video:
            res, dur, size = m
            return f"{res[0]}x{res[1]}, {dur:.1f}s, {size//1024} KB"
        else:
            res, size = m
            return f"{res[0]}x{res[1]}, {size//1024} KB"

    def _resize_keep_aspect(self, img: Image.Image, max_w: int, max_h: int):
        orig_w, orig_h = img.size
        if orig_w == 0 or orig_h == 0:
            return img.resize((max_w, max_h), Image.Resampling.LANCZOS)
        ratio = min(max_w / orig_w, max_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    def _resize_keep_aspect_tk(self, img: Image.Image, max_w: int, max_h: int):
        """Return a PhotoImage resized to fit in box, preserving aspect."""
        resized = self._resize_keep_aspect(img, max_w, max_h)
        return ImageTk.PhotoImage(resized)

    def play_videos(self):
        """Start video playback loops on both canvases."""
        # Open captures
        self.cap_left = cv2.VideoCapture(self.item_path1)
        self.cap_right = cv2.VideoCapture(self.item_path2)
        # Begin frame loop
        self._play_frame()

    def _play_frame(self):
        if self.decision_made:
            # stop playback
            if hasattr(self, 'cap_left'):
                self.cap_left.release()
            if hasattr(self, 'cap_right'):
                self.cap_right.release()
            return

        ret1, frame1 = (False, None)
        ret2, frame2 = (False, None)
        if hasattr(self, 'cap_left'):
            ret1, frame1 = self.cap_left.read()
        if hasattr(self, 'cap_right'):
            ret2, frame2 = self.cap_right.read()

        if ret1:
            self._display_on_canvas(frame1, self.canvas1)
        if ret2:
            self._display_on_canvas(frame2, self.canvas2)

        if ret1 or ret2:
            # schedule next frame ~30fps
            self.master.after(33, self._play_frame)
        else:
            # end reached
            if hasattr(self, 'cap_left'):
                self.cap_left.release()
            if hasattr(self, 'cap_right'):
                self.cap_right.release()

    def _display_on_canvas(self, frame, canvas):
        """Resize a BGR frame to fit in canvas box, preserving aspect, then display."""
        h_box, w_box = self.box_h, self.box_w  # note: box_h=360, box_w=640 in video mode
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
        """Restart video playback from start."""
        if hasattr(self, 'cap_left'):
            self.cap_left.release()
        if hasattr(self, 'cap_right'):
            self.cap_right.release()
        self.play_videos()

    def toggle_help(self):
        """Show/hide help label."""
        if self.help_label.winfo_viewable():
            self.help_label.pack_forget()
        else:
            self.help_label.pack(pady=5)

    def decision(self, choice):
        """Called when user makes a choice."""
        self.decision_made = True
        # release any open video captures
        if hasattr(self, 'cap_left'):
            self.cap_left.release()
        if hasattr(self, 'cap_right'):
            self.cap_right.release()
        self.master.destroy()
        # call the provided callback
        self.on_decision(choice)


# Helper functions to launch the window for images or videos:
def review_image_pair(path1, path2, meta1, meta2, similarity, on_decision, cluster_index=None, cluster_total=None):
    # Launch an image-review window
    root = tk.Tk()
    ReviewWindow(root, path1, path2, meta1, meta2, similarity, on_decision, video=False, cluster_index=cluster_index, cluster_total=cluster_total)
    root.mainloop()

def review_video_pair(path1, path2, meta1, meta2, similarity, on_decision, cluster_index=None, cluster_total=None):
    # Launch a video-review window.
    root = tk.Tk()
    ReviewWindow(root, path1, path2, meta1, meta2, similarity, on_decision, video=True, cluster_index=cluster_index, cluster_total=cluster_total)
    root.mainloop()
