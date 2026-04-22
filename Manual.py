"""
Manual.py  —  launched by Main.py as:  python Manual.py <width> <height>

Fullscreen transparent overlay.
• Click to place 4 corners.
• Drag any corner to reposition it (yellow = last-touched corner).
• Magnifier is a separate fully-opaque window — not affected by overlay alpha.
• Scroll wheel changes zoom level.
• Preview button toggles the interpolated grid.
• Confirm saves Grid.txt and exits.
• ESC cancels.
"""

import sys
import ctypes
import ctypes.wintypes
import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab, Image, ImageTk, ImageDraw
import numpy as np


# ── DPI awareness — must be set BEFORE tkinter initialises ─────────────────────
def _init_dpi():
    """
    Declare Per-Monitor DPI awareness and return the scale factor.
    Must run before tkinter starts so window coords stay in logical pixels
    while ImageGrab.grab() captures at full physical resolution.
    """
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-Monitor v2
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)   # Per-Monitor v1
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()         # System aware

        class _PT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        hmon = ctypes.windll.user32.MonitorFromPoint(_PT(0, 0), 1)
        dx   = ctypes.c_uint()
        dy   = ctypes.c_uint()
        ctypes.windll.shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy))
        return dx.value / 96.0
    except Exception:
        try:
            return ctypes.windll.user32.GetDpiForSystem() / 96.0
        except Exception:
            return 1.0

_DPI_SCALE = _init_dpi()


# ── argument parsing ───────────────────────────────────────────────────────────
def parse_args():
    if len(sys.argv) < 3:
        messagebox.showerror("Manual.py", "Usage: Manual.py <width> <height> [zoom_multiplier]")
        sys.exit(1)
    try:
        w, h = int(sys.argv[1]), int(sys.argv[2])
        if w <= 0 or h <= 0:
            raise ValueError
        zm  = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        hov = sys.argv[4] == "1" if len(sys.argv) > 4 else False
        gap = int(sys.argv[5])  if len(sys.argv) > 5 else 2
        return w, h, zm, hov, gap
    except ValueError:
        messagebox.showerror("Manual.py", "Invalid arguments.")
        sys.exit(1)


# ── geometry ───────────────────────────────────────────────────────────────────
def sort_corners(pts):
    s      = sorted(pts, key=lambda p: p[1])
    top    = sorted(s[:2], key=lambda p: p[0])
    bottom = sorted(s[2:], key=lambda p: p[0])
    return top[0], top[1], bottom[1], bottom[0]   # TL TR BR BL


def bilinear_grid(tl, tr, br, bl, cols, rows):
    tl, tr, br, bl = [np.array(p, dtype=float) for p in (tl, tr, br, bl)]
    pts = []
    for row in range(rows):
        v     = row / (rows - 1) if rows > 1 else 0.0
        left  = tl + v * (bl - tl)
        right = tr + v * (br - tr)
        for col in range(cols):
            u  = col / (cols - 1) if cols > 1 else 0.0
            pt = left + u * (right - left)
            pts.append((round(float(pt[0])), round(float(pt[1]))))
    return pts


def expand_hover_grid(pts, cols, rows, gap):
    """
    Expand a cols×rows grid of points into 2×2 clusters separated by gap pixels.
    Returns list of (x, y) tuples in row-major order (left→right, top→bottom).
    """
    step    = 2 * (1 + gap)   # cluster_size * (1 + gap_multiplier)
    grid_2d = [[pts[r*cols + c] for c in range(cols)] for r in range(rows)]

    rv = [[None]*cols for _ in range(rows)]
    dv = [[None]*cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            ox, oy = grid_2d[r][c]
            if c + 1 < cols:
                nx, ny = grid_2d[r][c+1]
                rv[r][c] = ((nx-ox)/step, (ny-oy)/step)
            elif c > 0:
                px, py = grid_2d[r][c-1]
                rv[r][c] = ((ox-px)/step, (oy-py)/step)
            else:
                rv[r][c] = (1.0, 0.0)
            if r + 1 < rows:
                nx2, ny2 = grid_2d[r+1][c]
                dv[r][c] = ((nx2-ox)/step, (ny2-oy)/step)
            elif r > 0:
                px2, py2 = grid_2d[r-1][c]
                dv[r][c] = ((ox-px2)/step, (oy-py2)/step)
            else:
                dv[r][c] = (0.0, 1.0)

    result = []
    for r in range(rows):
        for dr in range(2):
            for c in range(cols):
                for dc in range(2):
                    ox, oy = grid_2d[r][c]
                    px_ = round(ox + dc * rv[r][c][0] + dr * dv[r][c][0])
                    py_ = round(oy + dc * rv[r][c][1] + dr * dv[r][c][1])
                    result.append((px_, py_))
    return result



# ── overlay ────────────────────────────────────────────────────────────────────
class OverlayApp(tk.Tk):
    # handles
    DOT_R = 8
    HIT_R = 16

    # colours
    C_IDLE    = "#f38ba8"
    C_HOT     = "#ffdd57"
    C_LINE    = "#7c6af7"
    C_GRID    = "#a6e3a1"
    C_TEXT    = "#ffffff"
    C_CONFIRM = "#a6e3a1"
    C_PREVIEW = "#7c6af7"
    C_CANCEL  = "#f38ba8"

    # magnifier
    MAG_SIZE      = 160
    MAG_ZOOM      = 4.0
    MAG_ZOOM_MIN  = 1.5
    MAG_ZOOM_MAX  = 12.0
    MAG_ZOOM_STEP = 0.5
    MAG_OFFSET    = 30

    def __init__(self, grid_w, grid_h, zoom_multiplier=1.0, hover_mode=False, hover_gap=2):
        super().__init__()
        self.grid_w          = grid_w
        self.grid_h          = grid_h
        self._zoom_mult      = zoom_multiplier
        self._hover_mode     = hover_mode
        self._hover_gap      = hover_gap

        self.corners: list[list[int]] = []
        self._drag_idx: int | None    = None
        self._hot_idx:  int | None    = None
        self._preview_on              = False
        self._mag_zoom                = self.MAG_ZOOM
        self._bg_shot: Image.Image | None = None
        self._mag_photo               = None
        self._mag_win: tk.Toplevel | None = None
        self._drag_anchor: tuple | None   = None   # (mouse_x, mouse_y, corner_x, corner_y)

        self._dpi_scale  = _DPI_SCALE
        self._setup_window()
        self._draw_hud()
        self._bind_events()

    # ── window ─────────────────────────────────────────────────────────────────
    def _setup_window(self):
        # After SetProcessDpiAwareness, winfo_screenwidth returns physical pixels.
        # We need logical pixels for window geometry — divide by scale.
        phys_w = self.winfo_screenwidth()
        phys_h = self.winfo_screenheight()
        sw = round(phys_w / _DPI_SCALE)
        sh = round(phys_h / _DPI_SCALE)
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
            text=(f"Click 4 corners  ({self.grid_w}×{self.grid_h})  •  "
                  f"drag to adjust  •  scroll to zoom magnifier  •  ESC to cancel"),
            fill=self.C_TEXT, font=("Segoe UI", 14, "bold"), tags="hud")
        self._id_counter = self.canvas.create_text(
            sw // 2, 60,
            text="0 / 4 corners placed",
            fill="#fab387", font=("Segoe UI", 12), tags="hud")
        self._id_zoom = self.canvas.create_text(
            sw // 2, 82,
            text=f"Magnifier zoom: {self._mag_zoom:.1f}×",
            fill="#6e6e8e", font=("Segoe UI", 10), tags="hud")

        btn_y = 112
        self._btn_preview = self._make_btn(sw // 2 - 130, btn_y, "Preview",  self.C_PREVIEW, dim=True)
        self._btn_confirm = self._make_btn(sw // 2,        btn_y, "Confirm",  self.C_CONFIRM, dim=True)
        self._btn_cancel  = self._make_btn(sw // 2 + 130,  btn_y, "Cancel",   self.C_CANCEL,  dim=False)

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
        self.canvas.bind("<MouseWheel>",      self._on_scroll)   # Windows
        self.canvas.bind("<Button-4>",        self._on_scroll)   # Linux up
        self.canvas.bind("<Button-5>",        self._on_scroll)   # Linux down
        self.bind("<Escape>", lambda e: (self._restore_main(), self.destroy()))

    def _on_press(self, event):
        x, y = event.x, event.y

        if self._btn_hit(self._btn_cancel, x, y):
            self._restore_main(); self.destroy(); return
        if len(self.corners) == 4:
            if self._btn_hit(self._btn_confirm, x, y):
                self._confirm(); return
            if self._btn_hit(self._btn_preview, x, y):
                self._toggle_preview(); return

        for i, (cx, cy) in enumerate(self.corners):
            if abs(x - cx) <= self.HIT_R and abs(y - cy) <= self.HIT_R:
                self._drag_idx    = i
                self._hot_idx     = i
                self._drag_anchor = (x, y, cx, cy)   # mouse start + corner start
                self._grab_bg_screenshot()
                self.canvas.configure(cursor="fleur")
                self._redraw()
                return

        if len(self.corners) < 4:
            self.corners.append([x, y])
            self._hot_idx = len(self.corners) - 1
            self._redraw()
            if len(self.corners) == 4:
                self._btn_set_dim(self._btn_confirm, False)
                self._btn_set_dim(self._btn_preview, False)

    def _on_drag(self, event):
        if self._drag_idx is None or self._drag_anchor is None:
            return
        ax, ay, cx, cy = self._drag_anchor
        # scale mouse delta by 1/(zoom * multiplier) for finer control
        sensitivity = self._mag_zoom * self._zoom_mult
        dx = (event.x - ax) / sensitivity
        dy = (event.y - ay) / sensitivity
        new_x = round(cx + dx)
        new_y = round(cy + dy)
        self.corners[self._drag_idx] = [new_x, new_y]
        self._redraw()
        if self._preview_on:
            self._draw_grid_preview()
        self._draw_magnifier(new_x, new_y)   # follow the corner, not the mouse

    def _on_release(self, event):
        if self._drag_idx is not None:
            self._drag_idx    = None
            self._drag_anchor = None
            self._bg_shot     = None
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
            cx, cy = self.corners[self._drag_idx]
            self._draw_magnifier(cx, cy)

    # ── screenshot ─────────────────────────────────────────────────────────────
    def _grab_bg_screenshot(self):
        """Hide overlay, grab screen at physical resolution, restore."""
        self.attributes("-alpha", 0.0)
        self.update()
        # all_screens=False is fine; include_layered_windows=False avoids
        # capturing the (hidden) overlay itself on some Windows versions.
        # We rely on SetProcessDpiAwareness having been called so that
        # ImageGrab returns physical pixels.
        try:
            self._bg_shot = ImageGrab.grab(all_screens=False)
        except TypeError:
            # older Pillow doesn't support all_screens keyword
            self._bg_shot = ImageGrab.grab()
        self.attributes("-alpha", 0.45)

    # ── magnifier (fully opaque Toplevel — unaffected by overlay alpha) ────────
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
        # NO -alpha set here — window is fully opaque by default

        c = tk.Canvas(w, width=win_w, height=win_h,
                      bg="#1a1a2e", highlightthickness=0)
        c.pack()

        self._mag_win    = w
        self._mag_canvas = c

    def _draw_magnifier(self, mx, my):
        if self._bg_shot is None:
            return

        self._ensure_mag_window()

        size  = self.MAG_SIZE
        zoom  = self._mag_zoom
        scale = self._dpi_scale   # physical px per logical px
        half  = max(1, int(size / zoom / 2))

        # convert logical corner coords → physical screenshot coords
        pmx   = int(mx * scale)
        pmy   = int(my * scale)
        phalf = max(1, int(half * scale))

        src_x0 = max(0, pmx - phalf)
        src_y0 = max(0, pmy - phalf)
        src_x1 = min(self._bg_shot.width,  pmx + phalf)
        src_y1 = min(self._bg_shot.height, pmy + phalf)

        crop = self._bg_shot.crop((src_x0, src_y0, src_x1, src_y1))
        crop = crop.resize((size, size), Image.NEAREST)

        # circular crop onto solid background
        bg   = Image.new("RGB", (size, size), (26, 26, 46))
        mask = Image.new("L",   (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        bg.paste(crop.convert("RGB"), mask=mask)
        self._mag_photo = ImageTk.PhotoImage(bg)

        label_h = 22
        win_w   = size + 4
        win_h   = size + 4 + label_h
        r       = size // 2
        cx      = r + 2
        cy      = r + 2

        mc = self._mag_canvas
        mc.delete("all")

        mc.create_image(cx, cy, image=self._mag_photo, anchor="center")
        mc.create_oval(2, 2, size + 2, size + 2,
                       outline=self.C_HOT, width=2)
        ch = 10
        mc.create_line(cx - ch, cy, cx + ch, cy, fill=self.C_HOT, width=1)
        mc.create_line(cx, cy - ch, cx, cy + ch, fill=self.C_HOT, width=1)
        mc.create_text(cx, size + 4 + label_h // 2,
                       text=f"{mx}, {my}  •  {self._mag_zoom:.1f}×",
                       fill=self.C_HOT, font=("Segoe UI", 9, "bold"))

        # position next to cursor, flip at screen edges
        offset = self.MAG_OFFSET + r
        px = mx + offset
        py = my - offset - r
        if px + win_w > self.sw:
            px = mx - offset - win_w
        if py < 0:
            py = my + self.MAG_OFFSET
        if py + win_h > self.sh:
            py = self.sh - win_h - 4

        self._mag_win.geometry(f"{win_w}x{win_h}+{px}+{py}")
        self._mag_win.deiconify()

    def _hide_magnifier(self):
        if self._mag_win is not None and self._mag_win.winfo_exists():
            self._mag_win.withdraw()

    # ── drawing ────────────────────────────────────────────────────────────────
    def _redraw(self):
        self.canvas.delete("corners")
        n = len(self.corners)
        self.canvas.itemconfigure(self._id_counter,
                                  text=f"{n} / 4 corners placed")
        if n == 0:
            return

        loop = self.corners + ([self.corners[0]] if n == 4 else [])
        for i in range(len(loop) - 1):
            x0, y0 = loop[i];  x1, y1 = loop[i + 1]
            self.canvas.create_line(x0, y0, x1, y1,
                                    fill=self.C_LINE, width=2,
                                    dash=(6, 3), tags="corners")

        r = self.DOT_R
        for i, (cx, cy) in enumerate(self.corners):
            col = self.C_HOT if i == self._hot_idx else self.C_IDLE
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                    fill=col, outline="white", width=1,
                                    tags="corners")
            self.canvas.create_text(cx + r + 5, cy, text=str(i + 1),
                                    fill=col, font=("Segoe UI", 9, "bold"),
                                    anchor="w", tags="corners")

        self.canvas.tag_raise("hud")
        self.canvas.tag_raise("btn")

    def _draw_grid_preview(self):
        self.canvas.delete("grid")
        if len(self.corners) < 4:
            return
        tl, tr, br, bl = sort_corners(self.corners)
        pts = bilinear_grid(tl, tr, br, bl, self.grid_w, self.grid_h)
        if self._hover_mode:
            pts = expand_hover_grid(pts, self.grid_w, self.grid_h, self._hover_gap)
        dr = 2
        for (gx, gy) in pts:
            self.canvas.create_oval(gx-dr, gy-dr, gx+dr, gy+dr,
                                    fill=self.C_GRID, outline="", tags="grid")
        self.canvas.tag_raise("corners")
        self.canvas.tag_raise("hud")
        self.canvas.tag_raise("btn")

    def _toggle_preview(self):
        self._preview_on = not self._preview_on
        self.canvas.itemconfigure(self._btn_preview[1],
                                  text="Preview ✔" if self._preview_on else "Preview")
        if self._preview_on:
            self._draw_grid_preview()
        else:
            self.canvas.delete("grid")

    # ── restore Main.py ───────────────────────────────────────────────────────
    def _restore_main(self):
        import subprocess, sys, os
        # Find and restore any minimized Main.py window via a tiny helper
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_restore_main.py")
        if os.path.isfile(helper):
            subprocess.Popen([sys.executable, helper])

    # ── confirm ────────────────────────────────────────────────────────────────
    def _confirm(self):
        tl, tr, br, bl = sort_corners(self.corners)
        pts = bilinear_grid(tl, tr, br, bl, self.grid_w, self.grid_h)
        if self._hover_mode:
            pts = expand_hover_grid(pts, self.grid_w, self.grid_h, self._hover_gap)
        try:
            with open("Grid.txt", "w") as f:
                for pt in pts:
                    f.write(f"{pt}\n")
        except Exception as e:
            self.destroy()
            self._restore_main()
            messagebox.showerror("Manual.py", f"Failed to save Grid.txt:\n{e}")
            return
        self.destroy()
        self._restore_main()
        n = len(pts)
        messagebox.showinfo("Manual.py",
                            f"Grid saved to Grid.txt\n"
                            f"{self.grid_w}×{self.grid_h}"
                            f"{' (hover: '+str(n)+' pts)' if self._hover_mode else ' = '+str(n)+' points'}")


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    for pkg, name in [("numpy", "numpy"), ("PIL", "Pillow")]:
        try:
            __import__(pkg)
        except ImportError:
            messagebox.showerror("Missing dependency",
                                 f"{name} is required.\nRun:  pip install {name}")
            sys.exit(1)

    grid_w, grid_h, zoom_mult, hover_mode, hover_gap = parse_args()
    app = OverlayApp(grid_w, grid_h, zoom_mult, hover_mode, hover_gap)
    app.mainloop()
