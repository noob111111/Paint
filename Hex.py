"""
Hex.py  —  launched by Main.py (no arguments needed)

Fullscreen transparent overlay.
• Click 1 point.
• Drag to reposition (yellow = last-touched).
• Magnifier follows dragged point; scroll wheel changes zoom.
• Confirm saves screen coordinate to Variables.txt line 1 and exits.
• ESC or Cancel closes without saving.
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab, Image, ImageTk, ImageDraw


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VARS_FILE  = os.path.join(SCRIPT_DIR, "Variables.txt")


def _read_settings_lines():
    """Return lines 2+ of Variables.txt, or empty list if file missing."""
    if not os.path.isfile(VARS_FILE):
        return []
    try:
        with open(VARS_FILE) as f:
            lines = f.readlines()
        return lines[1:] if len(lines) > 1 else []
    except Exception:
        return []


# ── overlay ────────────────────────────────────────────────────────────────────
class HexPicker(tk.Tk):
    DOT_R = 8
    HIT_R = 16

    C_IDLE    = "#f38ba8"
    C_HOT     = "#ffdd57"
    C_LINE    = "#7c6af7"
    C_TEXT    = "#ffffff"
    C_CONFIRM = "#a6e3a1"
    C_CANCEL  = "#f38ba8"

    MAG_SIZE      = 160
    MAG_ZOOM      = 4.0
    MAG_ZOOM_MIN  = 1.5
    MAG_ZOOM_MAX  = 12.0
    MAG_ZOOM_STEP = 0.5
    MAG_OFFSET    = 30

    def __init__(self):
        super().__init__()

        self.points: list[list[int]] = []
        self._drag_idx: int | None   = None
        self._hot_idx:  int | None   = None
        self._mag_zoom                = self.MAG_ZOOM
        self._bg_shot: Image.Image | None = None
        self._mag_photo               = None
        self._mag_win: tk.Toplevel | None = None

        self._setup_window()
        self._draw_hud()
        self._bind_events()

    # ── window ─────────────────────────────────────────────────────────────────
    def _setup_window(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.sw, self.sh = sw, sh
        self.geometry(f"{sw}x{sh}+0+0")
        self.overrideredirect(True)
        self.attributes("-alpha", 0.45)
        self.configure(bg="black")
        self.attributes("-topmost", True)
        self.canvas = tk.Canvas(self, width=sw, height=sh,
                                bg="black", highlightthickness=0,
                                cursor="crosshair")
        self.canvas.pack()

    # ── HUD ────────────────────────────────────────────────────────────────────
    def _draw_hud(self):
        sw = self.sw
        self.canvas.create_text(
            sw // 2, 30,
            text="Click 1 point  •  drag to adjust  •  scroll to zoom magnifier  •  ESC to cancel",
            fill=self.C_TEXT, font=("Segoe UI", 14, "bold"), tags="hud")

        self._id_counter = self.canvas.create_text(
            sw // 2, 60,
            text="0 / 1 point placed",
            fill="#fab387", font=("Segoe UI", 12), tags="hud")

        self._id_zoom = self.canvas.create_text(
            sw // 2, 82,
            text=f"Magnifier zoom: {self._mag_zoom:.1f}×",
            fill="#6e6e8e", font=("Segoe UI", 10), tags="hud")

        btn_y = 112
        self._btn_confirm = self._make_btn(sw // 2 - 65,  btn_y, "Confirm", self.C_CONFIRM, dim=True)
        self._btn_cancel  = self._make_btn(sw // 2 + 65,  btn_y, "Cancel",  self.C_CANCEL,  dim=False)

    def _make_btn(self, cx, cy, label, color, w=110, h=32, dim=False):
        x0, y0, x1, y1 = cx-w//2, cy-h//2, cx+w//2, cy+h//2
        rid = self.canvas.create_rectangle(x0, y0, x1, y1, fill=color,
                                           outline="white", width=1,
                                           tags=("btn", label))
        tid = self.canvas.create_text(cx, cy, text=label, fill="black",
                                      font=("Segoe UI", 10, "bold"),
                                      tags=("btn", label))
        if dim:
            self.canvas.itemconfigure(rid, stipple="gray50")
        return (rid, tid, x0, y0, x1, y1, color)

    def _btn_hit(self, b, x, y):
        return b[2] <= x <= b[4] and b[3] <= y <= b[5]

    def _btn_set_dim(self, b, dim: bool):
        self.canvas.itemconfigure(b[0], stipple="gray50" if dim else "")

    # ── events ─────────────────────────────────────────────────────────────────
    def _bind_events(self):
        self.canvas.bind("<Button-1>",        self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>",      self._on_scroll)
        self.canvas.bind("<Button-4>",        self._on_scroll)
        self.canvas.bind("<Button-5>",        self._on_scroll)
        self.bind("<Escape>", lambda e: (self._restore_main(), self.destroy()))

    def _on_press(self, event):
        x, y = event.x, event.y

        if self._btn_hit(self._btn_cancel, x, y):
            self._restore_main(); self.destroy(); return
        if len(self.points) == 1 and self._btn_hit(self._btn_confirm, x, y):
            self._confirm(); return

        for i, (px, py) in enumerate(self.points):
            if abs(x - px) <= self.HIT_R and abs(y - py) <= self.HIT_R:
                self._drag_idx = i
                self._hot_idx  = i
                self._grab_bg_screenshot()
                self.canvas.configure(cursor="fleur")
                self._redraw()
                return

        if len(self.points) < 1:
            self.points.append([x, y])
            self._hot_idx = 0
            self._redraw()
            self._btn_set_dim(self._btn_confirm, False)

    def _on_drag(self, event):
        if self._drag_idx is None:
            return
        self.points[self._drag_idx] = [event.x, event.y]
        self._redraw()
        self._draw_magnifier(event.x, event.y)

    def _on_release(self, event):
        if self._drag_idx is not None:
            self._drag_idx = None
            self._bg_shot  = None
            self.canvas.configure(cursor="crosshair")
            self._hide_magnifier()
            self._redraw()

    def _on_scroll(self, event):
        direction = 1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4) else -1
        self._mag_zoom = max(self.MAG_ZOOM_MIN,
                             min(self.MAG_ZOOM_MAX,
                                 self._mag_zoom + direction * self.MAG_ZOOM_STEP))
        self.canvas.itemconfigure(self._id_zoom,
                                  text=f"Magnifier zoom: {self._mag_zoom:.1f}×")
        if self._drag_idx is not None:
            px, py = self.points[self._drag_idx]
            self._draw_magnifier(px, py)

    # ── screenshot ─────────────────────────────────────────────────────────────
    def _grab_bg_screenshot(self):
        self.attributes("-alpha", 0.0)
        self.update()
        self._bg_shot = ImageGrab.grab()
        self.attributes("-alpha", 0.45)

    # ── magnifier ──────────────────────────────────────────────────────────────
    def _ensure_mag_window(self):
        if self._mag_win is not None and self._mag_win.winfo_exists():
            return
        size    = self.MAG_SIZE
        label_h = 22
        win_w   = size + 4
        win_h   = size + 4 + label_h
        w = tk.Toplevel(self)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg="#1a1a2e")
        c = tk.Canvas(w, width=win_w, height=win_h,
                      bg="#1a1a2e", highlightthickness=0)
        c.pack()
        self._mag_win    = w
        self._mag_canvas = c

    def _draw_magnifier(self, mx, my):
        if self._bg_shot is None:
            return
        self._ensure_mag_window()
        size = self.MAG_SIZE
        zoom = self._mag_zoom
        half = max(1, int(size / zoom / 2))
        src_x0 = max(0, mx - half);  src_y0 = max(0, my - half)
        src_x1 = min(self._bg_shot.width, mx + half)
        src_y1 = min(self._bg_shot.height, my + half)
        crop = self._bg_shot.crop((src_x0, src_y0, src_x1, src_y1))
        crop = crop.resize((size, size), Image.NEAREST)
        bg   = Image.new("RGB", (size, size), (26, 26, 46))
        mask = Image.new("L",   (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        bg.paste(crop.convert("RGB"), mask=mask)
        self._mag_photo = ImageTk.PhotoImage(bg)
        label_h = 22; win_w = size + 4; win_h = size + 4 + label_h
        r = size // 2; cx = r + 2; cy = r + 2
        mc = self._mag_canvas
        mc.delete("all")
        mc.create_image(cx, cy, image=self._mag_photo, anchor="center")
        mc.create_oval(2, 2, size + 2, size + 2, outline=self.C_HOT, width=2)
        ch = 10
        mc.create_line(cx-ch, cy, cx+ch, cy, fill=self.C_HOT, width=1)
        mc.create_line(cx, cy-ch, cx, cy+ch, fill=self.C_HOT, width=1)
        mc.create_text(cx, size + 4 + label_h // 2,
                       text=f"{mx}, {my}  •  {self._mag_zoom:.1f}×",
                       fill=self.C_HOT, font=("Segoe UI", 9, "bold"))
        offset = self.MAG_OFFSET + r
        px = mx + offset;  py = my - offset - r
        if px + win_w > self.sw: px = mx - offset - win_w
        if py < 0:               py = my + self.MAG_OFFSET
        if py + win_h > self.sh: py = self.sh - win_h - 4
        self._mag_win.geometry(f"{win_w}x{win_h}+{px}+{py}")
        self._mag_win.deiconify()

    def _hide_magnifier(self):
        if self._mag_win is not None and self._mag_win.winfo_exists():
            self._mag_win.withdraw()

    # ── drawing ────────────────────────────────────────────────────────────────
    def _redraw(self):
        self.canvas.delete("points")
        n = len(self.points)
        self.canvas.itemconfigure(self._id_counter,
                                  text=f"{n} / 1 point placed")
        if n == 0:
            return
        r = self.DOT_R
        for i, (px, py) in enumerate(self.points):
            col = self.C_HOT if i == self._hot_idx else self.C_IDLE
            self.canvas.create_oval(px-r, py-r, px+r, py+r,
                                    fill=col, outline="white", width=1,
                                    tags="points")
            self.canvas.create_text(px + r + 5, py, text="Hex", fill=col,
                                    font=("Segoe UI", 10, "bold"),
                                    anchor="w", tags="points")
        self.canvas.tag_raise("hud")
        self.canvas.tag_raise("btn")

    # ── restore Main.py ────────────────────────────────────────────────────────
    def _restore_main(self):
        import subprocess, sys
        helper = os.path.join(SCRIPT_DIR, "_restore_main.py")
        if os.path.isfile(helper):
            subprocess.Popen([sys.executable, helper])

    # ── confirm ────────────────────────────────────────────────────────────────
    def _confirm(self):
        px, py = self.points[0]
        settings_lines = _read_settings_lines()
        try:
            with open(VARS_FILE, "w") as f:
                f.write(f"{(px, py)}\n")
                f.writelines(settings_lines)
        except Exception as e:
            self.destroy()
            self._restore_main()
            messagebox.showerror("Hex.py", f"Failed to save Variables.txt:\n{e}")
            return
        self.destroy()
        self._restore_main()
        messagebox.showinfo("Hex.py", f"Saved to Variables.txt:\n({px}, {py})")


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        from PIL import ImageGrab, Image, ImageTk, ImageDraw
    except ImportError:
        messagebox.showerror("Missing dependency",
                             "Pillow is required.\nRun:  pip install Pillow")
        sys.exit(1)

    app = HexPicker()
    app.mainloop()
