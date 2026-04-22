import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import subprocess
import sys
import os

# ── paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = {
    "converter": os.path.join(SCRIPT_DIR, "Converter.py"),
    "manual":    os.path.join(SCRIPT_DIR, "Manual.py"),
    "auto":      os.path.join(SCRIPT_DIR, "Auto.py"),
    "rgb":       os.path.join(SCRIPT_DIR, "Hex.py"),
    "paint":     os.path.join(SCRIPT_DIR, "Paint.py"),
    "imgcheck":  os.path.join(SCRIPT_DIR, "IMGCheck.py"),
}

VARS_FILE = os.path.join(SCRIPT_DIR, "Variables.txt")

# ── colours / fonts ────────────────────────────────────────────────────────────
BG         = "#1e1e2e"
PANEL_BG   = "#2a2a3d"
ACCENT     = "#7c6af7"
ACCENT_HOV = "#9d8fff"
BTN_FG     = "#ffffff"
MUTED      = "#6e6e8e"
TEXT       = "#cdd6f4"
SUCCESS    = "#a6e3a1"
WARNING    = "#fab387"

FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_BTN   = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_LABEL = ("Segoe UI", 9, "bold")

PREVIEW_W, PREVIEW_H = 380, 280

# ── default settings ───────────────────────────────────────────────────────────
DEFAULTS = {
    # Painting
    "paint_clicks":       5,
    "paint_click_delay":  5,     # ms between painting clicks
    "jiggle":             True,  # move 1px between clicks
    # Mouse movement
    "mouse_speed_pixel":  0.05,  # seconds per move to pixel
    "mouse_speed_hex":    0.0,   # seconds per move to hex field
    # Hex input
    "hex_clicks":         2,
    "hex_click_delay":    10,    # ms between hex clicks
    "hex_paste_delay":    20,    # ms after paste before enter
    # Experimental
    "blur":               False, # double grid resolution with averaged midpoints
    # Manual corners
    "zoom_multiplier":    1.0,   # how much zoom slows down corner dragging
    # Hover mode
    "hover_mode":         False, # expand each pixel into 2x2 cluster
    "hover_gap":          2,     # gap between clusters in pixels
}


# ── helpers ────────────────────────────────────────────────────────────────────
def run_script(key: str, extra_args: list[str] | None = None):
    path = SCRIPTS[key]
    if not os.path.isfile(path):
        messagebox.showerror("Script not found", f"Could not find:\n{path}")
        return None
    args = [sys.executable, path] + (extra_args or [])
    return subprocess.Popen(args)


def read_hex_coord():
    """Read line 1 of Variables.txt (the hex coordinate). Returns None if missing."""
    if not os.path.isfile(VARS_FILE):
        return None
    try:
        with open(VARS_FILE) as f:
            return f.readline().strip()
    except Exception:
        return None


def write_settings(settings: dict):
    """Write settings to Variables.txt lines 2+, preserving line 1 (hex coord)."""
    hex_line = read_hex_coord() or ""
    lines = [hex_line,
             str(settings["paint_clicks"]),
             str(settings["paint_click_delay"]),
             "1" if settings["jiggle"] else "0",
             str(settings["mouse_speed_pixel"]),
             str(settings["mouse_speed_hex"]),
             str(settings["hex_clicks"]),
             str(settings["hex_click_delay"]),
             str(settings["hex_paste_delay"]),
             "1" if settings["blur"] else "0",
             str(settings.get("grid_w", 51)),
             str(settings.get("grid_h", 39)),
             str(settings.get("zoom_multiplier", 1.0)),
             "1" if settings.get("hover_mode", False) else "0",
             str(settings.get("hover_gap", 2)),
             ]
    with open(VARS_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")


# ── settings window ────────────────────────────────────────────────────────────
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, settings: dict):
        super().__init__(parent)
        self.parent   = parent
        self.settings = dict(settings)
        self.title("Settings")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()   # modal
        self._vars = {}
        self._build()
        self._center()

    def _build(self):
        pad = 16

        # ── Painting ──────────────────────────────────────────────────────────
        self._section("🎨  Painting", pad)

        self._row("Clicks per pixel",
                  "paint_clicks", "int", pad,
                  hint="How many times to click each pixel")
        self._row("Delay between clicks  (ms)",
                  "paint_click_delay", "int", pad,
                  hint="Milliseconds between each painting click")
        self._toggle("Jiggle  (move 1 px between clicks)",
                     "jiggle", pad,
                     hint="Slightly moves mouse between clicks to help register")

        # ── Mouse Movement ────────────────────────────────────────────────────
        self._section("🖱  Mouse Movement", pad)

        self._row("Speed — pixel to pixel  (sec)",
                  "mouse_speed_pixel", "float", pad,
                  hint="Duration of mouse movement between pixels (0 = instant)")
        self._row("Speed — towards hex field  (sec)",
                  "mouse_speed_hex", "float", pad,
                  hint="Duration of mouse movement to the hex input (0 = instant)")

        # ── Hex Input ─────────────────────────────────────────────────────────
        self._section("🔤  Hex Input", pad)

        self._row("Clicks on hex field",
                  "hex_clicks", "int", pad,
                  hint="How many times to click the hex input field")
        self._row("Delay between hex clicks  (ms)",
                  "hex_click_delay", "int", pad,
                  hint="Milliseconds between each hex field click")
        self._row("Delay after paste  (ms)",
                  "hex_paste_delay", "int", pad,
                  hint="Milliseconds to wait after pasting before pressing Enter")

        # ── Manual Corners ────────────────────────────────────────────────────
        self._section("🎯  Manual Corners", pad)
        self._row("Zoom sensitivity multiplier",
                  "zoom_multiplier", "float", pad,
                  hint="Higher = slower dragging per zoom level (1.0 = default)")

        # ── Experimental ──────────────────────────────────────────────────────
        self._section("🧪  Experimental", pad)
        self._toggle("Blur  (double grid resolution + average colors)",
                     "blur", pad,
                     hint="Inserts midpoints between grid points and averages their colors")

        # ── Hover Mode ────────────────────────────────────────────────────────
        self._section("🎯  Hover Mode", pad)
        self._toggle("Hover mode  (2×2 clusters with gaps)",
                     "hover_mode", pad,
                     hint="Each pixel becomes a 2×2 cluster, clusters spaced by gap")
        self._row("Gap between clusters  (px)",
                  "hover_gap", "int", pad,
                  hint="0 = touching clusters, 1 = 1px gap, 2 = 2px gap (same size as cluster)")

        # ── buttons ───────────────────────────────────────────────────────────
        btn_frame = tk.Frame(self, bg=BG, padx=pad, pady=pad)
        btn_frame.pack(fill="x")

        save_btn = tk.Label(btn_frame, text="💾  Save", font=FONT_BTN,
                            bg=SUCCESS, fg="black", padx=14, pady=8,
                            cursor="hand2", relief="flat")
        save_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        save_btn.bind("<Button-1>", lambda e: self._save())

        cancel_btn = tk.Label(btn_frame, text="Cancel", font=FONT_BTN,
                              bg="#313244", fg=TEXT, padx=14, pady=8,
                              cursor="hand2", relief="flat")
        cancel_btn.pack(side="left", fill="x", expand=True)
        cancel_btn.bind("<Button-1>", lambda e: self.destroy())

    def _section(self, title, pad):
        tk.Frame(self, bg=MUTED, height=1).pack(fill="x", padx=pad, pady=(12, 0))
        tk.Label(self, text=title, font=FONT_TITLE,
                 bg=BG, fg=ACCENT).pack(anchor="w", padx=pad, pady=(6, 2))

    def _row(self, label, key, kind, pad, hint=""):
        frame = tk.Frame(self, bg=BG, padx=pad, pady=2)
        frame.pack(fill="x")
        tk.Label(frame, text=label, font=FONT_SMALL,
                 bg=BG, fg=TEXT, width=32, anchor="w").pack(side="left")
        var = tk.StringVar(value=str(self.settings[key]))
        self._vars[key] = (var, kind)
        e = tk.Entry(frame, textvariable=var, width=8,
                     bg="#313244", fg=TEXT, insertbackground=TEXT,
                     relief="flat", font=FONT_SMALL, justify="center")
        e.pack(side="left", ipady=3)
        if hint:
            tk.Label(frame, text=f"  {hint}", font=("Segoe UI", 8),
                     bg=BG, fg=MUTED).pack(side="left", padx=(6, 0))

    def _toggle(self, label, key, pad, hint=""):
        frame = tk.Frame(self, bg=BG, padx=pad, pady=2)
        frame.pack(fill="x")
        tk.Label(frame, text=label, font=FONT_SMALL,
                 bg=BG, fg=TEXT, width=32, anchor="w").pack(side="left")
        var = tk.BooleanVar(value=bool(self.settings[key]))
        self._vars[key] = (var, "bool")
        cb = tk.Checkbutton(frame, variable=var, bg=BG,
                            activebackground=BG, selectcolor="#313244",
                            fg=TEXT, cursor="hand2")
        cb.pack(side="left")
        if hint:
            tk.Label(frame, text=f"  {hint}", font=("Segoe UI", 8),
                     bg=BG, fg=MUTED).pack(side="left", padx=(6, 0))

    def _save(self):
        new = {}
        for key, (var, kind) in self._vars.items():
            raw = var.get()
            try:
                if kind == "int":
                    new[key] = int(raw)
                elif kind == "float":
                    new[key] = float(raw)
                elif kind == "bool":
                    new[key] = bool(var.get())
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"'{raw}' is not a valid value for '{key}'.")
                return
        self.parent.settings.update(new)
        write_settings(self.parent.settings)
        self.destroy()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")


# ── main window ────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Toolkit")
        self.configure(bg=BG)
        self.resizable(False, False)

        self._tk_image: ImageTk.PhotoImage | None = None
        self.settings = dict(DEFAULTS)

        self._build_ui()
        self._center()
        self.update_idletasks()
        self._normal_geometry = self.geometry()

        # write default settings on first run if file missing
        if not os.path.isfile(VARS_FILE):
            write_settings(self.settings)
        else:
            self._load_settings()
        self.after(100, self._update_estimate)

    def _load_settings(self):
        """Read settings from lines 2+ of Variables.txt."""
        try:
            with open(VARS_FILE) as f:
                lines = [l.strip() for l in f.readlines()]
            if len(lines) >= 9:
                self.settings["paint_clicks"]       = int(lines[1])
                self.settings["paint_click_delay"]  = int(lines[2])
                self.settings["jiggle"]             = lines[3] == "1"
                self.settings["mouse_speed_pixel"]  = float(lines[4])
                self.settings["mouse_speed_hex"]    = float(lines[5])
                self.settings["hex_clicks"]         = int(lines[6])
                self.settings["hex_click_delay"]    = int(lines[7])
                self.settings["hex_paste_delay"]    = int(lines[8])
            if len(lines) >= 10:
                self.settings["blur"]   = lines[9] == "1"
            if len(lines) >= 12:
                self.settings["grid_w"] = int(lines[10])
                self.settings["grid_h"] = int(lines[11])
            if len(lines) >= 13:
                self.settings["zoom_multiplier"] = float(lines[12])
            if len(lines) >= 14:
                self.settings["hover_mode"] = lines[13] == "1"
            if len(lines) >= 15:
                self.settings["hover_gap"]  = int(lines[14])
        except Exception:
            pass   # keep defaults if file is malformed

    # ── layout ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── header ──
        hdr = tk.Frame(self, bg=ACCENT, padx=18, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🖼  Image Toolkit", font=("Segoe UI", 15, "bold"),
                 bg=ACCENT, fg=BTN_FG).pack(side="left")

        # settings button top-right
        settings_btn = tk.Label(hdr, text="⚙", font=("Segoe UI", 15),
                                bg=ACCENT, fg=BTN_FG, cursor="hand2", padx=6)
        settings_btn.pack(side="right")
        settings_btn.bind("<Button-1>", lambda e: self._open_settings())
        settings_btn.bind("<Enter>",    lambda e: settings_btn.configure(fg="#ffdd57"))
        settings_btn.bind("<Leave>",    lambda e: settings_btn.configure(fg=BTN_FG))

        # ── main body ──
        body = tk.Frame(self, bg=BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        # left column – preview
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 14))

        tk.Label(left, text="Preview", font=FONT_TITLE,
                 bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 6))

        self.canvas = tk.Canvas(left, width=PREVIEW_W, height=PREVIEW_H,
                                bg=PANEL_BG, highlightthickness=2,
                                highlightbackground=ACCENT)
        self.canvas.pack()
        self._placeholder()

        self.lbl_path = tk.Label(left, text="No image loaded",
                                 font=FONT_SMALL, bg=BG, fg=MUTED,
                                 wraplength=PREVIEW_W, justify="left")
        self.lbl_path.pack(anchor="w", pady=(6, 0))

        # right column – buttons
        right = tk.Frame(body, bg=BG)
        right.pack(side="right", fill="y")

        tk.Label(right, text="Actions", font=FONT_TITLE,
                 bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 10))

        # ── resolution controls ──
        res_frame = tk.Frame(right, bg=PANEL_BG, padx=10, pady=8)
        res_frame.pack(fill="x", pady=(0, 6))

        tk.Label(res_frame, text="Resolution", font=FONT_LABEL,
                 bg=PANEL_BG, fg=TEXT).grid(row=0, column=0, columnspan=4,
                                            sticky="w", pady=(0, 6))

        tk.Label(res_frame, text="W", font=FONT_SMALL,
                 bg=PANEL_BG, fg=MUTED).grid(row=1, column=0, padx=(0, 4))
        self.var_w = tk.StringVar(value="51")
        tk.Entry(res_frame, textvariable=self.var_w, width=5,
                 bg="#313244", fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=FONT_SMALL, justify="center"
                 ).grid(row=1, column=1, padx=(0, 8), ipady=4)

        tk.Label(res_frame, text="H", font=FONT_SMALL,
                 bg=PANEL_BG, fg=MUTED).grid(row=1, column=2, padx=(0, 4))
        self.var_h = tk.StringVar(value="39")
        tk.Entry(res_frame, textvariable=self.var_h, width=5,
                 bg="#313244", fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=FONT_SMALL, justify="center"
                 ).grid(row=1, column=3, ipady=4)

        self._sep(right)

        self._make_btn(right, "➕  Add Image",
                       self._add_image, color=ACCENT, hover=ACCENT_HOV)
        self._sep(right)

        tk.Label(right, text="Corner Detection", font=FONT_SMALL,
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(4, 2))
        self._make_btn(right, "🖱  Get Corners  (manual)",
                       self._run_corners_manual, color="#313244", hover="#45475a")
        self._make_btn(right, "⚡  Get Corners  (auto, experimental)",
                       self._run_corners_auto,   color="#313244", hover="#45475a")
        self._sep(right)

        self._make_btn(right, "🎨  Get Hex",
                       self._run_rgb,   color="#1e3a5f", hover="#265080")
        self._make_btn(right, "🖌  Paint",
                       self._run_paint, color="#1a3a2a", hover="#245234")
        self._make_btn(right, "🔍  Check Image",
                       lambda: run_script("imgcheck"), color="#2a2a3d", hover="#3a3a5a")

        # ── time estimate bar ──
        self.lbl_estimate = tk.Label(self, text="Time estimate: —",
                                     font=FONT_SMALL, bg="#13131f", fg=MUTED,
                                     anchor="w", padx=12, pady=3)
        self.lbl_estimate.pack(fill="x", side="bottom")

        # ── status bar ──
        self.status = tk.Label(self, text="Ready", font=FONT_SMALL,
                               bg=PANEL_BG, fg=MUTED, anchor="w", padx=12, pady=4)
        self.status.pack(fill="x", side="bottom")

    def _make_btn(self, parent, text, cmd, color, hover):
        btn = tk.Label(parent, text=text, font=FONT_BTN,
                       bg=color, fg=BTN_FG,
                       padx=14, pady=10, cursor="hand2",
                       width=28, anchor="w", relief="flat")
        btn.pack(fill="x", pady=3)
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>",    lambda e: btn.configure(bg=hover))
        btn.bind("<Leave>",    lambda e: btn.configure(bg=color))
        return btn

    def _sep(self, parent):
        tk.Frame(parent, bg=MUTED, height=1).pack(fill="x", pady=6)

    # ── settings ───────────────────────────────────────────────────────────────
    def _open_settings(self):
        win = SettingsWindow(self, self.settings)
        self.wait_window(win)
        self._update_estimate()

    def _update_estimate(self):
        import ast as _ast
        grid_file = os.path.join(SCRIPT_DIR, "Grid.txt")
        rgb_file  = os.path.join(SCRIPT_DIR, "rgb_values.txt")
        if not os.path.isfile(grid_file) or not os.path.isfile(rgb_file):
            self.lbl_estimate.configure(text="Time estimate: — (run Add Image + Get Corners first)")
            return
        try:
            with open(rgb_file) as f:
                colors = [l.strip() for l in f if l.strip()]
        except Exception:
            self.lbl_estimate.configure(text="Time estimate: could not read files")
            return

        s   = self.settings
        gw  = s.get("grid_w", 51)
        gh  = s.get("grid_h", 39)

        # ── pixel count ───────────────────────────────────────────────────────
        hover = s.get("hover_mode", False)
        gap   = s.get("hover_gap", 2)
        blur  = s.get("blur", False)

        if hover and blur:
            hcols    = gw * 2
            hrows    = gh * 2
            n_fake   = (2*hcols - 1) * (2*hrows - 1) - (hcols * hrows)
            n_real   = hcols * hrows
            n_pixels = n_fake + n_real
            n_color_changes = len(set(colors)) * 2
        elif hover:
            n_pixels        = gw * gh * 4
            n_color_changes = len(set(colors))
        elif blur:
            n_fake   = (2*gw - 1) * (2*gh - 1) - (gw * gh)
            n_real   = gw * gh
            n_pixels = n_fake + n_real
            n_color_changes = len(set(colors)) * 2
        else:
            n_pixels        = len(colors)
            n_color_changes = len(set(colors))

        # ── per-pixel time ────────────────────────────────────────────────────
        clicks     = s["paint_clicks"]
        hold_s     = 0.005                              # hold inside each click
        delay_s    = s["paint_click_delay"] / 1000      # between clicks
        click_time = clicks * hold_s + max(0, clicks - 1) * delay_s
        move_time  = s["mouse_speed_pixel"]
        per_pixel  = move_time + click_time

        # ── per-color-change time ─────────────────────────────────────────────
        hc          = s["hex_clicks"]
        hdelay_s    = s["hex_click_delay"] / 1000
        hpaste_s    = s["hex_paste_delay"] / 1000
        hold_s      = 0.005
        hex_click_t = hc * hold_s + max(0, hc - 1) * hdelay_s
        hex_move_t  = s["mouse_speed_hex"]
        # ctrl+a x2 (5ms each) + 20ms focus wait + paste + paste_delay + enter ~10ms
        # typewrite 7 chars at ~20ms each (pyautogui default even at interval=0)
        hex_type_t  = 7 * 0.02
        hex_input_t = 0.02 + 0.005*2 + hex_type_t + hpaste_s + 0.01
        per_color   = hex_move_t + hex_click_t + hex_input_t

        total_sec = n_pixels * per_pixel + n_color_changes * per_color + 3

        if total_sec < 60:
            est = f"{total_sec:.0f}s"
        elif total_sec < 3600:
            est = f"{total_sec/60:.1f} min"
        else:
            est = f"{total_sec/3600:.1f} hr"

        n_colors  = len(set(colors))
        mode_note = ""
        if s.get("hover_mode", False) and s.get("blur", False): mode_note = "  (hover + blur)"
        elif s.get("hover_mode", False): mode_note = "  (hover)"
        elif s.get("blur", False): mode_note = "  (blur, 2 passes)"
        self.lbl_estimate.configure(
            text=f"⏱  ~{est}{mode_note}  —  {n_pixels} px, {n_colors} colors, {n_color_changes} color changes")

    # ── preview helpers ─────────────────────────────────────────────────────────
    def _placeholder(self):
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, PREVIEW_W, PREVIEW_H, fill=PANEL_BG, outline="")
        self.canvas.create_text(PREVIEW_W // 2, PREVIEW_H // 2,
                                text="No image loaded",
                                fill=MUTED, font=("Segoe UI", 11))

    def _show_preview(self, path: str):
        img = Image.open(path)
        img.thumbnail((PREVIEW_W, PREVIEW_H), Image.LANCZOS)
        self._tk_image = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        x = (PREVIEW_W - img.width)  // 2
        y = (PREVIEW_H - img.height) // 2
        self.canvas.create_rectangle(0, 0, PREVIEW_W, PREVIEW_H, fill=PANEL_BG, outline="")
        self.canvas.create_image(x, y, anchor="nw", image=self._tk_image)

    # ── button actions ──────────────────────────────────────────────────────────
    def _add_image(self):
        res = self._get_resolution()
        if not res:
            return
        w, h = res
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                       ("All files", "*.*")]
        )
        if not path:
            return
        self._show_preview(path)
        short = os.path.basename(path)
        # if hover mode, converter gets the effective (expanded) resolution
        if self.settings.get("hover_mode", False):
            ew, eh = w * 2, h * 2
            self.lbl_path.configure(text=f"📄 {short}  →  {w}×{h}  (hover: {ew}×{eh})", fg=TEXT)
            self._set_status(f"Running Converter.py at {ew}×{eh} (hover) …", ACCENT)
            run_script("converter", [path, str(ew), str(eh)])
        else:
            self.lbl_path.configure(text=f"📄 {short}  →  {w}×{h}", fg=TEXT)
            self._set_status(f"Running Converter.py at {w}×{h} …", ACCENT)
            run_script("converter", [path, str(w), str(h)])

    def _get_resolution(self):
        try:
            w = int(self.var_w.get())
            h = int(self.var_h.get())
            if w <= 0 or h <= 0:
                raise ValueError
            return w, h
        except ValueError:
            messagebox.showerror("Invalid resolution",
                                 "Width and Height must be positive integers.")
            return None

    def _restore_self(self):
        self.deiconify()
        self.geometry(self._normal_geometry)
        self.lift()
        self.focus_force()

    def _run_corners_manual(self):
        res = self._get_resolution()
        if res:
            self.iconify()
            zm  = str(self.settings.get("zoom_multiplier", 1.0))
            hov = "1" if self.settings.get("hover_mode", False) else "0"
            gap = str(self.settings.get("hover_gap", 2))
            proc = run_script("manual", [str(res[0]), str(res[1]), zm, hov, gap])
            self._watch_proc(proc)

    def _run_corners_auto(self):
        res = self._get_resolution()
        if res:
            run_script("auto", [str(res[0]), str(res[1])])

    def _run_paint(self):
        res = self._get_resolution()
        if res:
            self.settings["grid_w"], self.settings["grid_h"] = res
            write_settings(self.settings)
        self.iconify()
        run_script("paint")

    def _run_rgb(self):
        self.iconify()
        proc = run_script("rgb")
        self._watch_proc(proc)

    def _watch_proc(self, proc):
        if proc is None:
            return
        def _poll():
            if proc.poll() is not None:
                self._restore_self()
            else:
                self.after(200, _poll)
        self.after(200, _poll)

    # ── misc ────────────────────────────────────────────────────────────────────
    def _set_status(self, msg: str, color: str = TEXT):
        self.status.configure(text=f"  {msg}", fg=color)
        self.after(4000, lambda: self.status.configure(text="  Ready", fg=MUTED))

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        from PIL import Image, ImageTk
    except ImportError:
        import tkinter.messagebox as mb
        mb.showerror("Missing dependency",
                     "Pillow is required.\nRun:  pip install Pillow")
        sys.exit(1)

    app = App()
    app.mainloop()
