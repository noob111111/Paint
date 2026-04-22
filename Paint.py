"""
Paint.py  —  launched by Main.py (no arguments needed)

Variables.txt format:
  Line 1:  (x, y)   hex input field coordinate  (Hex.py)
  Line 2:  int      paint_clicks
  Line 3:  int      paint_click_delay  (ms)
  Line 4:  0/1      jiggle
  Line 5:  float    mouse_speed_pixel  (seconds)
  Line 6:  float    mouse_speed_hex    (seconds)
  Line 7:  int      hex_clicks
  Line 8:  int      hex_click_delay    (ms)
  Line 9:  int      hex_paste_delay    (ms)
  Line 10: 0/1      blur
  Line 11: int      grid_w
  Line 12: int      grid_h

ESC while painting  → pauses and shows progress window
ESC / X on window   → exits
"""

import sys
import ast
import time
import ctypes
import ctypes.wintypes
import threading
import tkinter as tk
from tkinter import messagebox
from collections import defaultdict

try:
    import pyautogui
    pyautogui.FAILSAFE = False   # we handle abort ourselves via ESC
    pyautogui.PAUSE    = 0.0
except ImportError:
    messagebox.showerror("Missing dependency",
                         "pyautogui is required.\nRun:  pip install pyautogui")
    sys.exit(1)


# ── Win32 SendInput ─────────────────────────────────────────────────────────────
_user32   = ctypes.windll.user32
_SCREEN_W = _user32.GetSystemMetrics(0)
_SCREEN_H = _user32.GetSystemMetrics(1)

_INPUT_MOUSE          = 0
_MOUSEEVENTF_MOVE     = 0x0001
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP   = 0x0004
_MOUSEEVENTF_ABSOLUTE = 0x8000

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]
    _anonymous_ = ("_u",)
    _fields_    = [("type", ctypes.c_ulong), ("_u", _U)]

def _abs(x, y):
    return int(x * 65535 / max(_SCREEN_W - 1, 1)), int(y * 65535 / max(_SCREEN_H - 1, 1))

def _move(x, y):
    ax, ay = _abs(x, y)
    inp = _INPUT(type=_INPUT_MOUSE,
                 mi=_MOUSEINPUT(dx=ax, dy=ay,
                                dwFlags=_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE))
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))

def _click(x, y, hold_ms=5):
    ax, ay = _abs(x, y)
    f  = _MOUSEEVENTF_ABSOLUTE
    dn = _INPUT(type=_INPUT_MOUSE, mi=_MOUSEINPUT(dx=ax, dy=ay, dwFlags=f | _MOUSEEVENTF_LEFTDOWN))
    up = _INPUT(type=_INPUT_MOUSE, mi=_MOUSEINPUT(dx=ax, dy=ay, dwFlags=f | _MOUSEEVENTF_LEFTUP))
    _user32.SendInput(1, ctypes.byref(dn), ctypes.sizeof(_INPUT))
    time.sleep(hold_ms / 1000)
    _user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(_INPUT))

def _smooth_move(x, y, duration):
    if duration <= 0:
        _move(x, y); return
    pt = ctypes.wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    sx, sy = pt.x, pt.y
    steps  = max(5, int(duration * 200))
    for i in range(1, steps + 1):
        t    = i / steps
        ease = 1 - (1 - t) ** 2
        _move(int(sx + (x - sx) * ease), int(sy + (y - sy) * ease))
        time.sleep(duration / steps)


# ── file parsers ────────────────────────────────────────────────────────────────
def load_rgb_values(path="rgb_values.txt"):
    values = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                values.append(line)
    return values

def load_grid(path="Grid.txt"):
    points = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                points.append(ast.literal_eval(line))
    return points

def load_variables(path="Variables.txt"):
    defaults = {
        "paint_clicks":      5,
        "paint_click_delay": 5,
        "jiggle":            True,
        "mouse_speed_pixel": 0.05,
        "mouse_speed_hex":   0.0,
        "hex_clicks":        2,
        "hex_click_delay":   10,
        "hex_paste_delay":   20,
        "blur":              False,
        "grid_w":            51,
        "grid_h":            39,
        "hover_mode":        False,
        "hover_gap":         2,
    }
    with open(path) as f:
        lines = [l.strip() for l in f.readlines()]
    hex_coord = ast.literal_eval(lines[0])
    s = defaults.copy()
    try:
        if len(lines) > 1:  s["paint_clicks"]      = int(lines[1])
        if len(lines) > 2:  s["paint_click_delay"] = int(lines[2])
        if len(lines) > 3:  s["jiggle"]            = lines[3] == "1"
        if len(lines) > 4:  s["mouse_speed_pixel"] = float(lines[4])
        if len(lines) > 5:  s["mouse_speed_hex"]   = float(lines[5])
        if len(lines) > 6:  s["hex_clicks"]        = int(lines[6])
        if len(lines) > 7:  s["hex_click_delay"]   = int(lines[7])
        if len(lines) > 8:  s["hex_paste_delay"]   = int(lines[8])
        if len(lines) > 9:  s["blur"]              = lines[9] == "1"
        if len(lines) > 10: s["grid_w"]            = int(lines[10])
        if len(lines) > 11: s["grid_h"]            = int(lines[11])
        if len(lines) > 12: s["zoom_multiplier"]   = float(lines[12])
        if len(lines) > 13: s["hover_mode"]        = lines[13] == "1"
        if len(lines) > 14: s["hover_gap"]         = int(lines[14])
    except Exception:
        pass
    return hex_coord, s


# ── grouping ────────────────────────────────────────────────────────────────────
def group_by_color(rgb_values, grid_points):
    if len(rgb_values) != len(grid_points):
        raise ValueError(
            f"rgb_values.txt has {len(rgb_values)} entries but "
            f"Grid.txt has {len(grid_points)}.")
    order     = []
    color_map = defaultdict(list)
    seen      = set()
    for rgb, pt in zip(rgb_values, grid_points):
        color_map[rgb].append(pt)
        if rgb not in seen:
            order.append(rgb)
            seen.add(rgb)
    return order, color_map


# ── blur ────────────────────────────────────────────────────────────────────────
def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

def _rgb_to_hex(r, g, b):
    return f"#{int(r):02X}{int(g):02X}{int(b):02X}"

def apply_blur(rgb_values, grid_points, cols, rows):
    grid_2d  = [[grid_points[r*cols + c] for c in range(cols)] for r in range(rows)]
    color_2d = [[rgb_values[ r*cols + c] for c in range(cols)] for r in range(rows)]
    new_cols  = 2 * cols - 1
    new_rows  = 2 * rows - 1
    new_grid   = []
    new_colors = []
    fake_mask  = []

    for r in range(new_rows):
        for c in range(new_cols):
            or_, oc = r // 2, c // 2
            if r % 2 == 0 and c % 2 == 0:
                new_grid.append(grid_2d[or_][oc])
                new_colors.append(color_2d[or_][oc])
                fake_mask.append(False)
            elif r % 2 == 0:
                x = (grid_2d[or_][oc][0] + grid_2d[or_][oc+1][0]) / 2
                y = (grid_2d[or_][oc][1] + grid_2d[or_][oc+1][1]) / 2
                a, b_ = _hex_to_rgb(color_2d[or_][oc]), _hex_to_rgb(color_2d[or_][oc+1])
                new_grid.append((round(x), round(y)))
                new_colors.append(_rgb_to_hex((a[0]+b_[0])//2,(a[1]+b_[1])//2,(a[2]+b_[2])//2))
                fake_mask.append(True)
            elif c % 2 == 0:
                x = (grid_2d[or_][oc][0] + grid_2d[or_+1][oc][0]) / 2
                y = (grid_2d[or_][oc][1] + grid_2d[or_+1][oc][1]) / 2
                a, b_ = _hex_to_rgb(color_2d[or_][oc]), _hex_to_rgb(color_2d[or_+1][oc])
                new_grid.append((round(x), round(y)))
                new_colors.append(_rgb_to_hex((a[0]+b_[0])//2,(a[1]+b_[1])//2,(a[2]+b_[2])//2))
                fake_mask.append(True)
            else:
                pts  = [grid_2d[or_][oc], grid_2d[or_][oc+1],
                        grid_2d[or_+1][oc], grid_2d[or_+1][oc+1]]
                rgbs = [_hex_to_rgb(color_2d[or_][oc]),   _hex_to_rgb(color_2d[or_][oc+1]),
                        _hex_to_rgb(color_2d[or_+1][oc]), _hex_to_rgb(color_2d[or_+1][oc+1])]
                x = sum(p[0] for p in pts) / 4
                y = sum(p[1] for p in pts) / 4
                new_grid.append((round(x), round(y)))
                new_colors.append(_rgb_to_hex(sum(r[0] for r in rgbs)//4,
                                              sum(r[1] for r in rgbs)//4,
                                              sum(r[2] for r in rgbs)//4))
                fake_mask.append(True)

    return new_colors, new_grid, fake_mask


# ── hover mode grid expansion ──────────────────────────────────────────────────
def expand_hover_grid(rgb_values, grid_points, cols, rows, gap):
    """
    Expand a cols×rows grid into 2×2 clusters separated by `gap` pixels.
    Each original pixel maps to 4 cluster points sharing the same color.
    Output is row-major: full expanded row by full expanded row, left→right top→bottom.
    Returns (new_rgb_values, new_grid_points).
    """
    step     = 2 + gap
    grid_2d  = [[grid_points[r*cols + c] for c in range(cols)] for r in range(rows)]
    color_2d = [[rgb_values[ r*cols + c] for c in range(cols)] for r in range(rows)]

    # pre-compute per-original-pixel right-vector and down-vector (1 step unit)
    rv = [[None]*cols for _ in range(rows)]   # right unit vector
    dv = [[None]*cols for _ in range(rows)]   # down unit vector
    for r in range(rows):
        for c in range(cols):
            ox, oy = grid_2d[r][c]
            if c + 1 < cols:
                nx, ny = grid_2d[r][c+1]
                rv[r][c] = ((nx-ox)/step, (ny-oy)/step)
            elif c > 0:
                px_, py_ = grid_2d[r][c-1]
                rv[r][c] = ((ox-px_)/step, (oy-py_)/step)
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

    # emit in true row-major order: for each expanded row (r*2+dr),
    # emit all columns left to right (c*2+dc)
    new_pts    = []
    new_colors = []
    for r in range(rows):
        for dr in range(2):
            for c in range(cols):
                for dc in range(2):
                    ox, oy = grid_2d[r][c]
                    px = round(ox + dc * rv[r][c][0] + dr * dv[r][c][0])
                    py = round(oy + dc * rv[r][c][1] + dr * dv[r][c][1])
                    new_pts.append((px, py))
                    new_colors.append(color_2d[r][c])

    return new_colors, new_pts


# ── progress window ─────────────────────────────────────────────────────────────
class ProgressWindow(tk.Tk):
    def __init__(self, total_colors, total_pixels):
        super().__init__()
        self.title("Paint.py")
        self.configure(bg="#1e1e2e")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._closed = False

        pad = 18; w = 400
        tk.Label(self, text="🖌  Painting…", font=("Segoe UI", 13, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(padx=pad, pady=(pad, 6), anchor="w")
        self._lbl_color = tk.Label(self, text="Starting…",
                                   font=("Segoe UI", 10), bg="#1e1e2e", fg="#fab387")
        self._lbl_color.pack(padx=pad, anchor="w")
        self._lbl_pixel = tk.Label(self, text="",
                                   font=("Segoe UI", 10), bg="#1e1e2e", fg="#6e6e8e")
        self._lbl_pixel.pack(padx=pad, anchor="w", pady=(2, 4))
        self._lbl_layer = tk.Label(self, text="",
                                   font=("Segoe UI", 10, "bold"), bg="#1e1e2e", fg="#7c6af7")
        self._lbl_layer.pack(padx=pad, anchor="w", pady=(0, 8))

        tk.Label(self, text="Colors", font=("Segoe UI", 9),
                 bg="#1e1e2e", fg="#6e6e8e").pack(padx=pad, anchor="w")
        bfc = tk.Frame(self, bg="#313244", height=10, width=w-pad*2)
        bfc.pack(padx=pad, fill="x", pady=(2, 8)); bfc.pack_propagate(False)
        self._bar_c = tk.Frame(bfc, bg="#7c6af7", width=0, height=10)
        self._bar_c.place(x=0, y=0, height=10)
        self._bar_c_total = total_colors; self._bar_c_w = w - pad*2

        tk.Label(self, text="Pixels", font=("Segoe UI", 9),
                 bg="#1e1e2e", fg="#6e6e8e").pack(padx=pad, anchor="w")
        bfp = tk.Frame(self, bg="#313244", height=10, width=w-pad*2)
        bfp.pack(padx=pad, fill="x", pady=(2, 12)); bfp.pack_propagate(False)
        self._bar_p = tk.Frame(bfp, bg="#a6e3a1", width=0, height=10)
        self._bar_p.place(x=0, y=0, height=10)
        self._bar_p_total = total_pixels; self._bar_p_w = w - pad*2

        self._lbl_status = tk.Label(self, text="",
                                    font=("Segoe UI", 10, "bold"),
                                    bg="#1e1e2e", fg="#ffdd57")
        self._lbl_status.pack(padx=pad, anchor="w", pady=(0, 8))

        tk.Button(self, text="✕  Close / Exit",
                  font=("Segoe UI", 9), bg="#f38ba8", fg="black",
                  relief="flat", padx=10, pady=6,
                  command=self._close).pack(padx=pad, pady=(0, pad), fill="x")

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda e: self._close())
        self._center()
        self.update()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def _close(self):
        self._closed = True

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)

    def hide(self):
        self.withdraw()

    def set_layer(self, text):
        self._lbl_layer.configure(text=text)
        self.update()

    def set_status(self, text):
        self._lbl_status.configure(text=text)
        self.update()

    def set_color(self, idx, total, rgb):
        self._lbl_color.configure(text=f"Color {idx+1} / {total}  —  {rgb}")
        filled = int((idx / max(total-1, 1)) * self._bar_c_w)
        self._bar_c.place(x=0, y=0, width=max(filled, 0), height=10)
        self.update()

    def set_pixel(self, done, total):
        self._lbl_pixel.configure(text=f"Pixel {done} / {total}")
        filled = int((done / max(total, 1)) * self._bar_p_w)
        self._bar_p.place(x=0, y=0, width=max(filled, 0), height=10)
        self.update()

    @property
    def closed(self):
        return self._closed


# ── ESC listener (runs in background thread) ────────────────────────────────────
class EscListener:
    """Listens for ESC key globally. Sets .pressed = True each time ESC is hit."""
    VK_ESCAPE = 0x1B

    def __init__(self):
        self.pressed   = False
        self._running  = True
        self._thread   = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        prev = 0
        while self._running:
            state = _user32.GetAsyncKeyState(self.VK_ESCAPE) & 0x8000
            if state and not prev:
                self.pressed = True
            prev = state
            time.sleep(0.02)

    def consume(self):
        self.pressed = False

    def stop(self):
        self._running = False


# ── paint a single pass of points ───────────────────────────────────────────────
def _paint_pass(pts_by_color, order, hex_coord, s, painted, prog,
                pixels_done, total_pixels, esc, layer_label):
    """
    Paint one ordered pass of points.
    Returns updated pixels_done, or None if closed/aborted.
    """
    paint_clicks    = s["paint_clicks"]
    paint_delay     = s["paint_click_delay"] / 1000
    jiggle          = s["jiggle"]
    speed_pixel     = s["mouse_speed_pixel"]
    speed_hex       = s["mouse_speed_hex"]
    hex_clicks      = s["hex_clicks"]
    hex_click_delay = s["hex_click_delay"] / 1000
    hex_paste_delay = s["hex_paste_delay"] / 1000

    prog.set_layer(layer_label)
    color_order = [c for c in order if pts_by_color.get(c)]
    n_colors    = len(color_order)

    for color_idx, rgb in enumerate(color_order):
        # ── check ESC / pause ──────────────────────────────────────────────────
        if esc.pressed:
            esc.consume()
            prog.set_status("⏸  Paused — press ESC or ✕ to exit")
            prog.show()
            # wait until closed or ESC pressed again
            while not prog.closed:
                if esc.pressed:
                    esc.consume()
                    prog._close()
                    break
                prog.update()
                time.sleep(0.05)
            prog.set_status("")
            if prog.closed:
                return None, pixels_done
            prog.hide()

        if prog.closed:
            return None, pixels_done

        prog.set_color(color_idx, n_colors, rgb)

        # ── set hex color ──────────────────────────────────────────────────────
        root_clip = tk.Tk(); root_clip.withdraw()
        root_clip.clipboard_clear()
        root_clip.clipboard_append(str(rgb))
        root_clip.update()

        _smooth_move(hex_coord[0], hex_coord[1], speed_hex)
        for i in range(hex_clicks):
            # always return to hex_coord first, then apply up/down jiggle offset
            jy = hex_coord[1] + (1 if i % 2 else 0)
            _move(hex_coord[0], hex_coord[1])   # snap back
            _move(hex_coord[0], jy)             # jiggle offset
            _click(hex_coord[0], jy)
            if i < hex_clicks - 1:
                time.sleep(hex_click_delay)

        time.sleep(0.02)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.005)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.005)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(hex_paste_delay)
        pyautogui.press("enter")
        root_clip.destroy()

        # ── paint pixels ───────────────────────────────────────────────────────
        for pt in pts_by_color[rgb]:
            if prog.closed: return None, pixels_done
            if esc.pressed: break
            if pt in painted: continue

            x, y = pt[0], pt[1]
            _smooth_move(x, y, speed_pixel)
            # jiggle pattern: (0,0) (1,0) (1,1) (0,1) — resets each pixel
            _jiggle = [(0,0),(1,0),(1,1),(0,1)]
            for i in range(paint_clicks):
                if jiggle and i > 0:
                    jox, joy = _jiggle[i % 4]
                    jx, jy   = x + jox, y + joy
                    _move(jx, jy)
                    _click(jx, jy)
                else:
                    _click(x, y)
                if i < paint_clicks - 1:
                    time.sleep(paint_delay)

            painted.add(pt)
            pixels_done += 1
            prog.set_pixel(pixels_done, total_pixels)

    return pixels_done, pixels_done


# ── main ────────────────────────────────────────────────────────────────────────
def paint(rgb_path="rgb_values.txt", grid_path="Grid.txt", var_path="Variables.txt"):
    try:
        rgb_values  = load_rgb_values(rgb_path)
        grid_points = load_grid(grid_path)
        hex_coord, s = load_variables(var_path)
    except FileNotFoundError as e:
        messagebox.showerror("Paint.py", f"File not found:\n{e}"); return
    except Exception as e:
        messagebox.showerror("Paint.py", f"Failed to read files:\n{e}"); return

    # ── hover mode ────────────────────────────────────────────────────────────
    # When hover is on:
    #   - rgb_values.txt was written by Converter at effective resolution (ew×eh)
    #   - Grid.txt was written by Manual.py at effective resolution (ew×eh)
    # Both are already at the same size — no expansion needed here.
    # We just validate they match.
    if s.get("hover_mode", False):
        gw, gh = s.get("grid_w", 51), s.get("grid_h", 39)
        ew, eh = gw * 2, gh * 2
        if len(rgb_values) != ew * eh:
            messagebox.showerror("Paint.py",
                f"Hover: rgb_values.txt has {len(rgb_values)} colors but expected "
                f"{ew}×{eh}={ew*eh}.\nRe-run Add Image with Hover mode ON.")
            return
        if len(grid_points) != ew * eh:
            messagebox.showerror("Paint.py",
                f"Hover: Grid.txt has {len(grid_points)} points but expected "
                f"{ew}×{eh}={ew*eh}.\nRe-run Get Corners with Hover mode ON.")
            return

    # ── apply blur ─────────────────────────────────────────────────────────────
    fake_mask = None
    if s.get("blur", False):
        if s.get("hover_mode", False):
            cols   = s.get("grid_w", 51) * 2
            rows_b = s.get("grid_h", 39) * 2
        else:
            cols, rows_b = s.get("grid_w", 51), s.get("grid_h", 39)
        if cols * rows_b != len(grid_points):
            messagebox.showerror("Paint.py",
                f"Blur: grid {cols}×{rows_b}={cols*rows_b} ≠ {len(grid_points)} points.")
            return
        try:
            rgb_values, grid_points, fake_mask = apply_blur(rgb_values, grid_points, cols, rows_b)
        except Exception as e:
            messagebox.showerror("Paint.py", f"Blur failed: {e}"); return

    # ── build passes ───────────────────────────────────────────────────────────
    # Each pass is a dict: color → [points]
    if fake_mask is not None:
        # Pass 1: fake (blur) points only
        fake_rgb   = [rgb_values[i]  for i in range(len(grid_points)) if fake_mask[i]]
        fake_pts   = [grid_points[i] for i in range(len(grid_points)) if fake_mask[i]]
        # Pass 2: real (original) points only
        real_rgb   = [rgb_values[i]  for i in range(len(grid_points)) if not fake_mask[i]]
        real_pts   = [grid_points[i] for i in range(len(grid_points)) if not fake_mask[i]]

        def _build_pass(rgb_list, pt_list):
            order_ = []
            cmap_  = defaultdict(list)
            seen_  = set()
            for rgb, pt in zip(rgb_list, pt_list):
                cmap_[rgb].append(pt)
                if rgb not in seen_:
                    order_.append(rgb); seen_.add(rgb)
            return order_, cmap_

        fake_order, fake_map = _build_pass(fake_rgb, fake_pts)
        real_order, real_map = _build_pass(real_rgb, real_pts)
        passes = [
            (fake_order, fake_map, "Layer 1 / 2  —  Blur (generated pixels)"),
            (real_order, real_map, "Layer 2 / 2  —  Real (original pixels)"),
        ]
        total_pixels = len(grid_points)
    else:
        try:
            order, color_map = group_by_color(rgb_values, grid_points)
        except ValueError as e:
            messagebox.showerror("Paint.py", str(e)); return
        passes       = [(order, color_map, "")]
        total_pixels = len(grid_points)

    total_colors = sum(len(p[0]) for p in passes)
    prog = ProgressWindow(total_colors, total_pixels)
    prog.hide()   # hidden until countdown done or paused

    # countdown (shown briefly)
    prog.show()
    for i in range(3, 0, -1):
        prog.set_status(f"Starting in {i}…")
        prog.update()
        time.sleep(1)
        if prog.closed:
            prog.destroy(); return
    prog.set_status("")
    prog.hide()

    esc     = EscListener()
    painted = set()
    pixels_done = 0

    for order_, cmap_, label in passes:
        result, pixels_done = _paint_pass(cmap_, order_, hex_coord, s, painted,
                             prog, pixels_done, total_pixels, esc, label)
        if result is None:
            esc.stop()
            prog.destroy()
            messagebox.showwarning("Paint.py",
                                   f"Stopped after {pixels_done} / {total_pixels} pixels.")
            return

    esc.stop()
    prog.destroy()
    messagebox.showinfo("Paint.py",
                        f"Done!\n{pixels_done} pixels painted.")


if __name__ == "__main__":
    paint()
