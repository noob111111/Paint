import sys
from PIL import Image
from tkinter import messagebox

def process_image(image_path, width, height):
    try:
        img = Image.open(image_path)
        img = img.resize((width, height), Image.LANCZOS)

        hex_values = []
        for y in range(img.size[1]):
            for x in range(img.size[0]):
                r, g, b = img.getpixel((x, y))[:3]
                hex_values.append(f"#{r:02X}{g:02X}{b:02X}")

        with open("rgb_values.txt", "w") as f:
            for h in hex_values:
                f.write(f"{h}\n")

        messagebox.showinfo("Success",
            f"Hex values extracted at {width}×{height} and saved to rgb_values.txt.")

    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        messagebox.showerror("Error", "Usage: Converter.py <image_path> <width> <height>")
        sys.exit(1)

    image_path = sys.argv[1]
    try:
        width  = int(sys.argv[2])
        height = int(sys.argv[3])
    except ValueError:
        messagebox.showerror("Error", "Width and height must be integers.")
        sys.exit(1)

    process_image(image_path, width, height)
