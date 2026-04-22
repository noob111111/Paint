"""
_restore_main.py — restores the minimized Main.py window to its normal size.
Uses SW_SHOWNORMAL (1) so Windows always uses the stored normal size,
not the minimized/tiny state that SW_RESTORE (9) can produce.
"""
import ctypes

def restore():
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "Image Toolkit")
    if hwnd:
        user32.ShowWindow(hwnd, 1)   # SW_SHOWNORMAL — always normal size
        user32.SetForegroundWindow(hwnd)

if __name__ == "__main__":
    restore()
