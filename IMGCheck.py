"""
IMGCheck.py  —  inverts Converter.py

Reads:
  rgb_values.txt  — one #RRGGBB hex color per line, row-major left→right top→bottom
  Variables.txt   — settings including grid_w, grid_h, hover_mode, hover_gap

Normal mode:  shows the image at grid resolution (one pixel per block).
Hover mode:   shows each block as a 2×2 cluster with gaps between clusters,
              matching the actual on-screen layout of the paint target.
"""

import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk, ImageDraw
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RGB_FILE   = os.path.join(SCRIPT_DIR, "rgb_values.txt")
VARS_FILE  = os.path.join(SCRIPT_DIR, "Variables.txt")

BG      = "#1e1e2e"
PANEL   = "#2a2a3d"
ACCENT  = "#7c6af7"
TEXT    = "#cdd6f4"
MUTED   = "#6e6e8e"
SUCCESS = "#a6e3a1"
WARNING = "#fab387"

GAP_COLOR = (40, 40, 60)      # dark gap between clusters in hover preview


# ── loaders ────────────────────────────────────────────────────────────────────
def load_settings():
    """Returns dict with grid_w, grid_h, hover_mode, hover_gap."""
    s = {"grid_w": 51, "grid_h": 39, "hover_mode": False, "hover_gap": 2}
    if not os.path.isfile(VARS_FILE):
        messagebox.showerror("IMGCheck", "Variables.txt not found.\nRun Main.py first.")
        return None
    with open(VARS_FILE) as f:
        lines = [l.strip() for l in f.readlines()]
    try:
        if len(lines) > 10: s["grid_w"]     = int(lines[10])
        if len(lines) > 11: s["grid_h"]     = int(lines[11])
        if len(lines) > 13: s["hover_mode"] = lines[13] == "1"
        if len(lines) > 14: s["hover_gap"]  = int(lines[14])
    except (IndexError, ValueError):
        pass
    return s


def load_hex_colors():
    if not os.path.isfile(RGB_FILE):
        messagebox.showerror("IMGCheck", "rgb_values.txt not found.\nRun Add Image first.")
        return None
    colors = []
    with open(RGB_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                colors.append(line)
    return colors


def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ── image builders ─────────────────────────────────────────────────────────────
def build_normal_image(colors, w, h):
    """One pixel per grid point."""
    if len(colors) != w * h:
        messagebox.showerror("IMGCheck",
            f"rgb_values.txt has {len(colors)} colors but "
            f"resolution is {w}×{h} = {w*h}.\nRe-run Add Image.")
        return None
    img = Image.new("RGB", (w, h))
    img.putdata([hex_to_rgb(c) for c in colors])
    return img


def build_hover_image(colors, w, h, gap):
    """
    w×h are the BASE resolution (e.g. 51×39).
    colors has w*2 × h*2 entries (the doubled resolution).
    Each 2×2 block of colors is drawn as a cluster, with gap pixels between clusters.
    Total image size: (w*(2+gap) - gap) × (h*(2+gap) - gap)
    """
    ew, eh = w * 2, h * 2
    if len(colors) != ew * eh:
        messagebox.showerror("IMGCheck",
            f"rgb_values.txt has {len(colors)} colors but "
            f"expected {ew}×{eh}={ew*eh}.\nRe-run Add Image with Hover mode ON.")
        return None

    step   = 2 * (1 + gap)   # cluster_size * (1 + gap_multiplier)
    img_w  = w * step - (step - 2)
    img_h  = h * step - (step - 2)
    img    = Image.new("RGB", (img_w, img_h), GAP_COLOR)

    # colors are in row-major order at doubled resolution
    # each 2×2 block in the doubled grid = one cluster in the image
    for row in range(h):
        for col in range(w):
            ox = col * step   # top-left x of this cluster in output image
            oy = row * step   # top-left y
            for dr in range(2):
                for dc in range(2):
                    c_idx = (row*2 + dr) * ew + (col*2 + dc)
                    img.putpixel((ox + dc, oy + dr), hex_to_rgb(colors[c_idx]))

    return img


# ── GUI ────────────────────────────────────────────────────────────────────────
class IMGCheckApp(tk.Tk):
    MAX_PREVIEW = 620

    def __init__(self, colors, s):
        super().__init__()
        self.title("IMGCheck — Paint Preview")
        self.configure(bg=BG)
        self.resizable(False, False)

        self._colors     = colors
        self._s          = s
        self._hover_on   = s["hover_mode"]   # current view mode
        self._tk_img     = None
        self._normal_img = None
        self._hover_img  = None

        self._build_images()
        self._build_ui()
        self._render()
        self._center()

    def _build_images(self):
        w, h, gap = self._s["grid_w"], self._s["grid_h"], self._s["hover_gap"]
        ew = s.get('eff_w', s['grid_w'])
        eh = s.get('eff_h', s['grid_h'])
        self._normal_img = build_normal_image(self._colors, ew, eh)  # full res
        if self._s["hover_mode"]:
            self._hover_img = build_hover_image(self._colors, w, h, gap)  # pass base dims

    def _build_ui(self):
        # header
        hdr = tk.Frame(self, bg=ACCENT, padx=16, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🖼  IMGCheck  —  Paint Preview",
                 font=("Segoe UI", 13, "bold"),
                 bg=ACCENT, fg="white").pack(side="left")

        # info bar
        info = tk.Frame(self, bg=PANEL, padx=14, pady=6)
        info.pack(fill="x")
        w, h = self._s["grid_w"], self._s["grid_h"]
        unique = len(set(self._colors))
        self._lbl_info = tk.Label(info, text="", font=("Segoe UI", 10), bg=PANEL, fg=TEXT)
        self._lbl_info.pack(side="left")
        tk.Label(info, text=f"   •   Unique colors: {unique}",
                 font=("Segoe UI", 10), bg=PANEL, fg=MUTED).pack(side="left")

        # toggle button (only shown if hover mode is enabled in settings)
        if self._s["hover_mode"]:
            tog_frame = tk.Frame(self, bg=BG, padx=14, pady=6)
            tog_frame.pack(fill="x")
            self._tog_btn = tk.Label(tog_frame, text="", font=("Segoe UI", 10, "bold"),
                                     padx=12, pady=6, cursor="hand2", relief="flat")
            self._tog_btn.pack(side="left")
            self._tog_btn.bind("<Button-1>", lambda e: self._toggle_view())
            self._update_toggle_label()

        # canvas area
        self._canvas_frame = tk.Frame(self, bg=BG, padx=14, pady=8)
        self._canvas_frame.pack()

        self._canvas = tk.Canvas(self._canvas_frame, bg=PANEL,
                                 highlightthickness=2, highlightbackground=ACCENT)
        self._canvas.pack()

        self._lbl_scale = tk.Label(self._canvas_frame, text="",
                                   font=("Segoe UI", 8), bg=BG, fg=MUTED)
        self._lbl_scale.pack(pady=(4, 0))

        # save button
        btn_frame = tk.Frame(self, bg=BG, padx=14)
        btn_frame.pack(fill="x", pady=(0, 14))
        save_btn = tk.Label(btn_frame, text="💾  Save as PNG",
                            font=("Segoe UI", 10, "bold"),
                            bg=SUCCESS, fg="black",
                            padx=14, pady=8, cursor="hand2", relief="flat")
        save_btn.pack(fill="x")
        save_btn.bind("<Button-1>", lambda e: self._save())
        save_btn.bind("<Enter>",    lambda e: save_btn.configure(bg="#c3f0c8"))
        save_btn.bind("<Leave>",    lambda e: save_btn.configure(bg=SUCCESS))

    def _update_toggle_label(self):
        if self._hover_on:
            self._tog_btn.configure(text="🔵  Showing: Hover layout  (click to switch to Normal)",
                                    bg="#1e3a5f", fg=TEXT)
        else:
            self._tog_btn.configure(text="⚪  Showing: Normal  (click to switch to Hover layout)",
                                    bg="#313244", fg=TEXT)

    def _toggle_view(self):
        self._hover_on = not self._hover_on
        self._update_toggle_label()
        self._render()

    def _render(self):
        img = self._hover_img if (self._hover_on and self._hover_img) else self._normal_img
        if img is None:
            return

        w, h  = img.size
        scale = min(self.MAX_PREVIEW / w, self.MAX_PREVIEW / h, 1.0)
        dw    = max(1, round(w * scale))
        dh    = max(1, round(h * scale))

        preview      = img.resize((dw, dh), Image.NEAREST)
        self._tk_img = ImageTk.PhotoImage(preview)

        self._canvas.configure(width=dw, height=dh)
        self._canvas.delete("all")
        self._canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        mode = "Hover layout" if self._hover_on else "Normal"
        gw, gh = self._s["grid_w"], self._s["grid_h"]
        if self._hover_on:
            gap  = self._s["hover_gap"]
            self._lbl_info.configure(
                text=f"Resolution: {gw}×{gh}  →  hover {w}×{h}  (gap={gap})")
        else:
            self._lbl_info.configure(text=f"Resolution: {gw}×{gh}  ({gw*gh} pixels)")

        if scale < 1.0:
            self._lbl_scale.configure(text=f"{mode} — scaled to {dw}×{dh}  (×{scale:.2f})")
        else:
            self._lbl_scale.configure(text=f"{mode} — actual pixel size")

        self.update_idletasks()
        self._center()

    def _save(self):
        img = self._hover_img if (self._hover_on and self._hover_img) else self._normal_img
        path = filedialog.asksaveasfilename(
            title="Save preview image",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return
        img.save(path)
        messagebox.showinfo("IMGCheck", f"Saved to:\n{path}")

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk(); root.withdraw()

    s = load_settings()
    if s is None: sys.exit(1)

    colors = load_hex_colors()
    if colors is None: sys.exit(1)

    # compute expected count based on hover mode
    gw, gh = s["grid_w"], s["grid_h"]
    if s["hover_mode"]:
        ew, eh   = gw * 2, gh * 2
        expected = ew * eh
        res_str  = f"{gw}×{gh} (hover → {ew}×{eh} = {expected})"
    else:
        ew, eh   = gw, gh
        expected = gw * gh
        res_str  = f"{gw}×{gh} = {expected}"

    if len(colors) != expected:
        messagebox.showerror("IMGCheck",
            f"rgb_values.txt has {len(colors)} colors but expected {res_str}.\n"
            "Re-run Add Image.")
        sys.exit(1)

    s["eff_w"] = ew
    s["eff_h"] = eh

    root.destroy()
    app = IMGCheckApp(colors, s)
    app.mainloop()
