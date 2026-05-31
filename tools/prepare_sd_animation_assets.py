"""Prepare M5 CoreS3 SD-card animation frames.

Input layout:
  source_root/
    xiao_hong/animations/idle/*.png|jpg
    xiao_hong/animations/chat/*.png|jpg
    ...
    zhang_zong/animations/idle/*.png|jpg

Output layout:
  out_root/
    xiao_hong/animations/idle/frame_0001.jpg
    ...

Every frame is letterboxed to 320x240 so the firmware can draw it full-screen
without cropping portrait or oversized source images.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps


PERSONAS = ("xiao_hong", "zhang_zong")
STATES = ("idle", "meet", "outdoor", "chat", "leave")
EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
SIZE = (320, 240)


def natural_key(path: Path) -> tuple:
    parts: list[object] = []
    token = ""
    for ch in path.stem:
        if ch.isdigit():
            token += ch
        else:
            if token:
                parts.append(int(token))
                token = ""
            parts.append(ch.lower())
    if token:
        parts.append(int(token))
    return tuple(parts)


def convert_frame(src: Path, dst: Path, bg: tuple[int, int, int]) -> None:
    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        image.thumbnail(SIZE, Image.Resampling.NEAREST)
        canvas = Image.new("RGBA", SIZE, (*bg, 255))
        x = (SIZE[0] - image.width) // 2
        y = (SIZE[1] - image.height) // 2
        canvas.alpha_composite(image, (x, y))
        canvas.convert("RGB").save(dst, "JPEG", quality=88, optimize=True)


def convert_dir(src_dir: Path, dst_dir: Path, bg: tuple[int, int, int]) -> int:
    frames = sorted(
        [p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in EXTS],
        key=natural_key,
    )
    dst_dir.mkdir(parents=True, exist_ok=True)
    for old in dst_dir.glob("frame_*.jpg"):
        old.unlink()
    for index, src in enumerate(frames, start=1):
        convert_frame(src, dst_dir / f"frame_{index:04d}.jpg", bg)
    return len(frames)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resize persona animation frames for CoreS3 SD cards.")
    parser.add_argument("source_root", type=Path, help="Folder containing xiao_hong/ and zhang_zong/.")
    parser.add_argument("--out", type=Path, default=Path("sd_ready"), help="Output SD-card root.")
    parser.add_argument("--bg", default="0,0,0", help="RGB background, default black.")
    args = parser.parse_args()

    bg = tuple(int(x.strip()) for x in args.bg.split(","))
    if len(bg) != 3 or any(v < 0 or v > 255 for v in bg):
        raise SystemExit("--bg must look like 0,0,0")

    total = 0
    for persona in PERSONAS:
        for state in STATES:
            src_dir = args.source_root / persona / "animations" / state
            if not src_dir.exists():
                print(f"[missing] {src_dir}")
                continue
            count = convert_dir(src_dir, args.out / persona / "animations" / state, bg)
            total += count
            print(f"[ok] {persona}/{state}: {count} frame(s)")

    print(f"Done. Copy {args.out} contents to the SD-card root. Converted {total} frame(s).")


if __name__ == "__main__":
    main()
