import sys
import json
import time
import threading
import queue
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

# Easing function for smooth slide
def ease_out_expo(x):
    return 1 if x == 1 else 1 - pow(2, -10 * x)

class MacOSNotifier:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        
        # Make the window click-through and non-activating where possible
        # WS_EX_NOACTIVATE = 0x08000000, WS_EX_TOOLWINDOW = 0x00000080
        # This prevents the window from stealing focus from games
        try:
            from ctypes import windll
            hwnd = windll.user32.GetParent(self.root.winfo_id())
            style = windll.user32.GetWindowLongW(hwnd, -20)
            windll.user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080)
        except Exception:
            pass

        # Use a chroma-key transparent background
        self.transparent_color = "#000001"
        self.root.config(bg=self.transparent_color)
        self.root.attributes("-transparentcolor", self.transparent_color)

        self.width = 340
        self.height = 70
        self.margin_x = 20
        self.margin_y = 40
        
        # Position off-screen initially
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        self.start_x = self.screen_width
        self.end_x = self.screen_width - self.width - self.margin_x
        self.y = self.margin_y
        
        self.root.geometry(f"{self.width}x{self.height}+{self.start_x}+{self.y}")

        # Create rounded background image
        self.bg_image = self.create_rounded_bg()
        self.bg_photo = ImageTk.PhotoImage(self.bg_image)
        
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height, 
                                bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")
        
        # Text placeholders
        self.title_text = self.canvas.create_text(
            55, 20, text="Notification", font=("Segoe UI", 11, "bold"), 
            fill="#ffffff", anchor="w"
        )
        self.msg_text = self.canvas.create_text(
            55, 45, text="Message goes here...", font=("Segoe UI", 9), 
            fill="#a0a0a0", anchor="w", width=270
        )
        
        # Icon placeholder
        self.icon_text = self.canvas.create_text(
            30, 35, text="ℹ", font=("Segoe UI Emoji", 16), 
            fill="#0a84ff", anchor="center"
        )

        self.queue = queue.Queue()
        self.is_animating = False
        self.current_toast_end_time = 0
        self.state = "hidden" # hidden, sliding_in, visible, sliding_out

        # Start checking queue
        self.root.after(50, self.check_queue)
        self.root.after(16, self.animate_loop)

    def create_rounded_bg(self):
        # Create a beautiful dark rounded rectangle matching macOS
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 1, 0)) # transparent matching key
        draw = ImageDraw.Draw(img)
        # Background
        draw.rounded_rectangle((0, 0, self.width-1, self.height-1), radius=12, fill=(30, 30, 30, 240))
        # Subtle border
        draw.rounded_rectangle((0, 0, self.width-1, self.height-1), radius=12, outline=(60, 60, 60, 255), width=1)
        return img

    def show(self, title, msg, icon_str="ℹ", icon_color="#0a84ff"):
        self.canvas.itemconfig(self.title_text, text=title)
        self.canvas.itemconfig(self.msg_text, text=msg)
        self.canvas.itemconfig(self.icon_text, text=icon_str, fill=icon_color)
        
        self.state = "sliding_in"
        self.anim_start_time = time.time()
        self.anim_duration = 0.6  # 600ms slide

    def hide(self):
        self.state = "sliding_out"
        self.anim_start_time = time.time()
        self.anim_duration = 0.5

    def animate_loop(self):
        now = time.time()
        
        if self.state == "sliding_in":
            progress = (now - self.anim_start_time) / self.anim_duration
            if progress >= 1.0:
                progress = 1.0
                self.state = "visible"
                self.current_toast_end_time = now + 4.0 # stay visible for 4 seconds
            
            eased = ease_out_expo(progress)
            current_x = int(self.start_x - (self.start_x - self.end_x) * eased)
            self.root.geometry(f"{self.width}x{self.height}+{current_x}+{self.y}")
            
        elif self.state == "visible":
            if now >= self.current_toast_end_time:
                # Check if there's another notification waiting, if so immediately swap?
                # For simplicity, we just hide, and the next one triggers after hide.
                self.hide()
                
        elif self.state == "sliding_out":
            progress = (now - self.anim_start_time) / self.anim_duration
            if progress >= 1.0:
                progress = 1.0
                self.state = "hidden"
            
            # Slide out is reverse, so we slide right
            # using an ease_in_like effect or just 1-ease_out
            eased = ease_out_expo(progress)
            current_x = int(self.end_x + (self.start_x - self.end_x) * eased)
            self.root.geometry(f"{self.width}x{self.height}+{current_x}+{self.y}")

        self.root.after(16, self.animate_loop) # ~60fps

    def check_queue(self):
        try:
            # Only process new toasts if we are hidden
            if self.state == "hidden":
                msg = self.queue.get_nowait()
                if msg:
                    if msg.get("type") == "score_popup":
                        self.show_score_popup(msg)
                    elif msg.get("type") == "rewatch_popup":
                        self.show_rewatch_popup(msg)
                    else:
                        icons = {
                            "success": ("✓", "#32d74b"),
                            "error": ("✕", "#ff453a"),
                            "info": ("ℹ", "#0a84ff"),
                            "star": ("★", "#ffd60a"),
                            "skip": ("⏭", "#bf5af2"),
                            "sync": ("⟳", "#30d158"),
                        }
                        icon_type = msg.get("icon", "info")
                        icon_str, icon_color = icons.get(icon_type, ("ℹ", "#0a84ff"))
                        self.show(msg.get("title", ""), msg.get("msg", ""), icon_str, icon_color)
        except queue.Empty:
            pass
            
        self.root.after(50, self.check_queue)

    def show_score_popup(self, msg_data):
        title = msg_data.get("title", "")
        media_id = msg_data.get("media_id")
        fmt = msg_data.get("format", "POINT_100")
        token = msg_data.get("token", "")

        popup = tk.Toplevel(self.root)
        popup.title("Rate This Anime")
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#1e1e1e")

        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        w, h = 320, 210
        x = screen_w - w - 20
        y = screen_h - h - 60
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.attributes("-alpha", 0.0)

        # Outer border
        outer = tk.Frame(popup, bg="#3a3a3a")
        outer.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(outer, bg="#1e1e1e")
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Label(inner, text="★  Rate This Anime", font=("Helvetica Neue", 12, "bold"),
                 fg="#ffd60a", bg="#1e1e1e").pack(pady=(14, 2))
        tk.Label(inner, text=f"{title}", font=("Helvetica Neue", 10),
                 fg="#a0a0a0", bg="#1e1e1e", wraplength=290).pack()

        score_var = tk.StringVar(value="")

        if fmt == "POINT_5":
            star_frame = tk.Frame(inner, bg="#1e1e1e")
            star_frame.pack(pady=10)
            star_btns = []
            selected = [0]
            def set_stars(n):
                selected[0] = n
                score_var.set(str(n))
                for i, b in enumerate(star_btns):
                    b.config(fg="#ffd60a" if i < n else "#444444")
            for i in range(1, 6):
                b = tk.Button(star_frame, text="★", font=("Helvetica Neue", 22),
                              bg="#1e1e1e", fg="#444444", bd=0, cursor="hand2",
                              activebackground="#1e1e1e", command=lambda n=i: set_stars(n))
                b.pack(side=tk.LEFT, padx=2)
                star_btns.append(b)
        elif fmt == "POINT_3":
            face_frame = tk.Frame(inner, bg="#1e1e1e")
            face_frame.pack(pady=8)
            for val, emoji, label in [(1, ":(", "Bad"), (2, ":|", "OK"), (3, ":)", "Great")]:
                tk.Button(face_frame, text=f"{emoji}\\n{label}", font=("Helvetica Neue", 11),
                          bg="#2a2a2a", fg="#ffffff", bd=0, cursor="hand2", width=5, height=2,
                          command=lambda v=val: score_var.set(str(v))).pack(side=tk.LEFT, padx=4)
        else:
            if fmt == "POINT_100":
                hint = "0 - 100"
            elif fmt == "POINT_10_DECIMAL":
                hint = "0.0 - 10.0"
            else:
                hint = "0 - 10"

            tk.Label(inner, text=f"Score ({hint})", font=("Helvetica Neue", 10),
                     fg="#a0a0a0", bg="#1e1e1e").pack(pady=(8, 2))
            entry = tk.Entry(inner, textvariable=score_var, font=("Helvetica Neue", 14),
                             bg="#2a2a2a", fg="#ffffff", insertbackground="white",
                             bd=0, justify="center", width=10)
            entry.pack(ipady=4)

        def _submit():
            raw = score_var.get().strip()
            if not raw:
                popup.destroy()
                return
            try:
                score_val = float(raw)
                if token and media_id:
                    import requests
                    mutation = '''
                    mutation ($mediaId: Int, $score: Float) {
                      SaveMediaListEntry(mediaId: $mediaId, score: $score) { id score }
                    }'''
                    r = requests.post(
                        "https://graphql.anilist.co",
                        json={"query": mutation, "variables": {"mediaId": media_id, "score": score_val}},
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)"},
                        timeout=8
                    )
                    if r.status_code == 200:
                        self.queue.put({"title": "AniList Score Saved!", "msg": f"{title} rated {raw}", "icon": "star"})
            except Exception as e:
                pass
            popup.destroy()

        btn_frame = tk.Frame(inner, bg="#1e1e1e")
        btn_frame.pack(pady=(8, 12))
        tk.Button(btn_frame, text="Save", font=("Helvetica Neue", 11, "bold"),
                  bg="#32d74b", fg="#ffffff", bd=0, padx=16, pady=5, cursor="hand2",
                  command=_submit).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Skip", font=("Helvetica Neue", 11),
                  bg="#2a2a2a", fg="#a0a0a0", bd=0, padx=16, pady=5, cursor="hand2",
                  command=popup.destroy).pack(side=tk.LEFT, padx=4)

        def fade_in():
            try:
                a = popup.attributes("-alpha")
                if a < 0.95:
                    popup.attributes("-alpha", min(a + 0.07, 0.95))
                    popup.after(16, fade_in)
            except Exception:
                pass
        popup.after(50, fade_in)


    def show_rewatch_popup(self, msg_data):
        title = msg_data.get("title", "")
        media_id = msg_data.get("media_id")
        current_repeat = msg_data.get("current_repeat", 0)
        token = msg_data.get("token", "")

        popup = tk.Toplevel(self.root)
        popup.title("Start Rewatch?")
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#1e1e1e")

        screen_w = popup.winfo_screenwidth()
        screen_h = popup.winfo_screenheight()
        w, h = 320, 160
        x = screen_w - w - 20
        y = screen_h - h - 60
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.attributes("-alpha", 0.0)

        # Outer border
        outer = tk.Frame(popup, bg="#3a3a3a")
        outer.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(outer, bg="#1e1e1e")
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Label(inner, text="↻  Start Rewatch?", font=("Helvetica Neue", 12, "bold"),
                 fg="#e84393", bg="#1e1e1e").pack(pady=(14, 2))
        tk.Label(inner, text=f"{title}", font=("Helvetica Neue", 10),
                 fg="#a0a0a0", bg="#1e1e1e", wraplength=290).pack()
        tk.Label(inner, text=f"Previous watches: {current_repeat}", font=("Helvetica Neue", 9, "italic"),
                 fg="#777777", bg="#1e1e1e").pack(pady=(2, 8))

        def _submit():
            target_repeat = current_repeat + 1
            if token and media_id:
                try:
                    import requests
                    mutation = '''
                    mutation ($mediaId: Int, $progress: Int, $status: MediaListStatus, $repeat: Int) {
                      SaveMediaListEntry(mediaId: $mediaId, progress: $progress, status: $status, repeat: $repeat) { id status repeat }
                    }'''
                    r = requests.post(
                        "https://graphql.anilist.co",
                        json={"query": mutation, "variables": {
                            "mediaId": media_id,
                            "progress": 0,
                            "status": "REPEATING",
                            "repeat": target_repeat
                        }},
                        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "VLC-RPC/6.1.8 (Windows NT 10.0; Win64; x64)"},
                        timeout=8
                    )
                    if r.status_code == 200:
                        # Success - queue toast and write signal file
                        self.queue.put({"title": "Rewatch Started!", "msg": f"{title} (Rewatch #{target_repeat})", "icon": "sync"})
                        
                        import os, json as _json
                        # Find the parent app directory
                        app_dir = os.path.dirname(os.path.abspath(__file__))
                        sig_dir = os.path.join(app_dir, "rewatch_signals")
                        os.makedirs(sig_dir, exist_ok=True)
                        sig_path = os.path.join(sig_dir, f"rewatch_started_{media_id}_{int(time.time())}.signal")
                        with open(sig_path, "w", encoding="utf-8") as sf:
                            _json.dump({"media_id": media_id, "repeat": target_repeat}, sf)
                except Exception as e:
                    pass
            popup.destroy()

        btn_frame = tk.Frame(inner, bg="#1e1e1e")
        btn_frame.pack(pady=(8, 12))
        tk.Button(btn_frame, text="Start Rewatch", font=("Helvetica Neue", 11, "bold"),
                  bg="#e84393", fg="#ffffff", bd=0, padx=16, pady=5, cursor="hand2",
                  command=_submit).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="Skip", font=("Helvetica Neue", 11),
                  bg="#2a2a2a", fg="#a0a0a0", bd=0, padx=16, pady=5, cursor="hand2",
                  command=popup.destroy).pack(side=tk.LEFT, padx=4)

        def fade_in():
            try:
                a = popup.attributes("-alpha")
                if a < 0.95:
                    popup.attributes("-alpha", min(a + 0.07, 0.95))
                    popup.after(16, fade_in)
            except Exception:
                pass
        popup.after(50, fade_in)


def stdin_reader(q):
    """Read lines from stdin and put them in the queue."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                # Parent process closed stdin / exited
                break
            data = json.loads(line.strip())
            q.put(data)
        except Exception:
            pass
    # Exit if stdin is broken (parent died)
    sys.exit(0)

def main():
    app = MacOSNotifier()
    
    # Start background thread to read from stdin
    t = threading.Thread(target=stdin_reader, args=(app.queue,), daemon=True)
    t.start()
    
    app.root.mainloop()

if __name__ == "__main__":
    main()
