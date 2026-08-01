"""
notifier.py - Custom macOS-style dark toast notifications for VLC RPC.
"""
import tkinter as tk
import threading
import time
import queue

TOAST_WIDTH = 340
TOAST_HEIGHT = 78
TOAST_MARGIN_X = 20
TOAST_MARGIN_Y = 50

# macOS-style dark palette
BG = "#1e1e1e"
BG_BORDER = "#3a3a3a"
TITLE_FG = "#ffffff"
MSG_FG = "#a0a0a0"

ICONS = {
    "success":  ("✓", "#32d74b"),
    "error":    ("✕", "#ff453a"),
    "info":     ("ℹ", "#0a84ff"),
    "star":     ("★", "#ffd60a"),
    "skip":     ("⏭", "#bf5af2"),
    "sync":     ("⟳", "#30d158"),
    "warning":  ("⚠", "#ff9f0a"),
}


class ToastNotification:
    """A single macOS-style dark toast popup."""

    def __init__(self, title, message, icon_type="info", duration=4000, y_offset=0):
        self.title = title
        self.message = message
        self.icon_type = icon_type
        self.duration = duration
        self.y_offset = y_offset  # stacking offset
        self.root = None

    def show(self, on_done_callback=None):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        self.root.configure(bg=BG)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - TOAST_WIDTH - TOAST_MARGIN_X
        y = screen_h - TOAST_HEIGHT - TOAST_MARGIN_Y - self.y_offset

        self.root.geometry(f"{TOAST_WIDTH}x{TOAST_HEIGHT}+{x}+{y}")

        # Outer border frame
        outer = tk.Frame(self.root, bg=BG_BORDER)
        outer.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        inner = tk.Frame(outer, bg=BG)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Icon
        icon_char, icon_color = ICONS.get(self.icon_type, ICONS["info"])
        icon_frame = tk.Frame(inner, bg=BG, width=46)
        icon_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(12, 0))
        icon_frame.pack_propagate(False)

        icon_lbl = tk.Label(
            icon_frame, text=icon_char,
            font=("Helvetica Neue", 22),
            fg=icon_color, bg=BG, anchor="center"
        )
        icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Text area
        text_frame = tk.Frame(inner, bg=BG)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 12), pady=10)

        title_lbl = tk.Label(
            text_frame, text=self.title,
            font=("Helvetica Neue", 12, "bold"),
            fg=TITLE_FG, bg=BG, anchor="w"
        )
        title_lbl.pack(fill=tk.X)

        msg_lbl = tk.Label(
            text_frame, text=self.message,
            font=("Helvetica Neue", 10),
            fg=MSG_FG, bg=BG, anchor="w",
            wraplength=TOAST_WIDTH - 90, justify="left"
        )
        msg_lbl.pack(fill=tk.BOTH, expand=True)

        # Click to dismiss
        def dismiss(event=None):
            self._fade_out(on_done_callback)

        for w in [self.root, outer, inner, icon_lbl, title_lbl, msg_lbl]:
            w.bind("<Button-1>", dismiss)

        # Animations
        def fade_in():
            a = self.root.attributes("-alpha")
            if a < 0.92:
                self.root.attributes("-alpha", min(a + 0.07, 0.92))
                self.root.after(16, fade_in)
            else:
                self.root.after(self.duration, lambda: self._fade_out(on_done_callback))

        self.root.after(50, fade_in)
        self.root.mainloop()

    def _fade_out(self, callback=None):
        try:
            a = self.root.attributes("-alpha")
            if a > 0.04:
                self.root.attributes("-alpha", max(a - 0.07, 0.0))
                self.root.after(16, lambda: self._fade_out(callback))
            else:
                self.root.destroy()
                if callback:
                    callback()
        except Exception:
            if callback:
                callback()


class ToastNotifier:
    """
    Thread-safe queue-based toast notification manager.
    Shows one toast at a time, stacked bottom-right.
    Usage:
        notifier.toast("Title", "Message", icon_type="success")
    """

    def __init__(self):
        self._queue = queue.Queue()
        self._active = False
        self._lock = threading.Lock()

    def toast(self, title, message, icon_type="info", duration=4000):
        """Queue a toast. Thread-safe, non-blocking."""
        self._queue.put((title, message, icon_type, duration))
        with self._lock:
            if not self._active:
                self._active = True
                t = threading.Thread(target=self._worker, daemon=True)
                t.start()

    def _worker(self):
        while True:
            try:
                title, message, icon_type, duration = self._queue.get(timeout=0.3)
            except queue.Empty:
                with self._lock:
                    self._active = False
                return

            done_event = threading.Event()
            def _show():
                ToastNotification(title, message, icon_type, duration).show(
                    on_done_callback=done_event.set
                )
            t = threading.Thread(target=_show, daemon=True)
            t.start()
            done_event.wait(timeout=duration / 1000 + 3)
            time.sleep(0.15)


# Singleton — import and use this everywhere
notifier = ToastNotifier()


if __name__ == "__main__":
    notifier.toast("VLC RPC", "Connected to Discord RPC!", icon_type="success")
    time.sleep(1.2)
    notifier.toast("AniList Sync", "Attack on Titan S4 E28 synced!", icon_type="sync")
    time.sleep(1.2)
    notifier.toast("AniSkip", "Opening detected — skipping...", icon_type="skip")
    time.sleep(1.2)
    notifier.toast("Rate This Anime", "You finished Jujutsu Kaisen! Rate it?", icon_type="star", duration=6000)
    time.sleep(10)
