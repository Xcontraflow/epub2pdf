"""
Generate icon.ico for EPUB2PDF.
Pixel art design: 16x16 base, scaled with NEAREST for crisp edges at all sizes.
"""

from PIL import Image

ACCENT = (212, 119, 74, 255)   # #D4774A
WHITE  = (255, 255, 255, 255)

# 16x16 pixel art grid.
# 0 = transparent (rounded corner cut)
# 1 = orange background
# 2 = white arrow
# Corners cut 2px (top/bottom outer) + 1px (next row) → classic pixel rounded square
_GRID = [
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],  # 0
    [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],  # 1
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],  # 2
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],  # 3
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],  # 4
    [1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1],  # 5  arrowhead top
    [1,1,1,1,1,1,1,1,1,1,1,2,2,1,1,1],  # 6
    [1,1,1,1,1,1,1,2,2,2,2,2,2,2,1,1],  # 7  shaft + head
    [1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,1],  # 8  TIP
    [1,1,1,1,1,1,1,2,2,2,2,2,2,2,1,1],  # 9
    [1,1,1,1,1,1,1,1,1,1,1,2,2,1,1,1],  # 10
    [1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1],  # 11 arrowhead bottom
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],  # 12
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],  # 13
    [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],  # 14
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],  # 15
]


def render(size: int) -> Image.Image:
    """Render pixel art icon — NEAREST scaling keeps edges razor-sharp."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    pix = img.load()
    for r, row in enumerate(_GRID):
        for c, val in enumerate(row):
            if val == 1:
                pix[c, r] = ACCENT
            elif val == 2:
                pix[c, r] = WHITE
    return img.resize((size, size), Image.NEAREST)


def make() -> None:
    # Multiples of 16 → perfect pixel scaling at every size
    sizes = [16, 32, 48, 64, 128, 256]
    images = [render(s) for s in sizes]
    images[0].save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print("icon.ico generated")


if __name__ == "__main__":
    make()
