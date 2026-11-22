from pathlib import Path

from PIL import Image, ImageDraw


root = Path(__file__).resolve().parent
scale = 4
canvas = Image.new("RGBA", (512 * scale, 512 * scale))
draw = ImageDraw.Draw(canvas)


def box(bounds):
    return tuple(round(value * scale) for value in bounds)


def rounded(bounds, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box(bounds), radius * scale, fill, outline, width * scale)


def circle(bounds, fill, outline=None, width=1):
    draw.ellipse(box(bounds), fill, outline, width * scale)


rounded((80, 128, 161, 178), 13, "#e5e9ed")
draw.polygon(
    [(round(horizontal * scale), round(vertical * scale)) for horizontal, vertical in
     [(174, 164), (203, 112), (307, 112), (338, 164)]],
    fill="#e5e9ed",
)
rounded((32, 156, 480, 410), 48, "#e5e9ed")
rounded((48, 172, 464, 394), 32, "#202b36")
rounded((64, 190, 448, 211), 10, "#364655")
rounded((393, 235, 445, 371), 17, "#34414d")
circle((138, 176, 354, 392), "#111923", "#e5e9ed", 13)
circle((164, 202, 328, 366), "#547888")
circle((179, 217, 313, 351), "#172f40")
circle((202, 240, 290, 328), "#30657b")
circle((213, 249, 279, 315), "#101f2c")
circle((197, 230, 232, 265), "#c3e8ec")
circle((267, 307, 283, 323), "#73a7b7")
rounded((361, 189, 407, 209), 6, "#e5e9ed")
circle((423, 189, 443, 209), "#e8c769")

icon = canvas.resize((512, 512), Image.Resampling.LANCZOS)
icon.save(root / "camera.png")
icon.save(root / "camera.ico", sizes=[(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
preview = Image.new("RGB", (700, 360), "#181b20")
preview.paste(icon.resize((320, 320), Image.Resampling.LANCZOS), (12, 20),
              icon.resize((320, 320), Image.Resampling.LANCZOS))
preview_draw = ImageDraw.Draw(preview)
for index, size in enumerate((16, 24, 32, 48, 64)):
    small = icon.resize((size, size), Image.Resampling.LANCZOS)
    left = 355 + index * 66
    preview.paste(small, (left, 160 - size // 2), small)
    preview_draw.text((left, 210), str(size), fill="#d7dde4")
preview.save(root / "preview.png")
print("Created camera.png, camera.ico and preview.png")
