#!/usr/bin/env python3
"""
把美术给的 PNG 帧转成 M5 CoreS3 能直接读的格式：
  - 等比缩放 + 居中铺到 320x240（屏幕分辨率，留白不裁切）
  - 输出 JPG，自动降质量直到单帧 < 140KB（板子内存限制）
  - 连号重命名 frame_0001.jpg, frame_0002.jpg ...
  - 输出到 SD 卡资源目录结构（见 docs/PROTOCOL.md §8）

依赖：pip install pillow

用法示例：
  # 把张总的 11 张表情图，作为"相遇"动画，输出到 SD 目录
  python tools/convert_frames.py animation_frame/boss/Boss ^
      --out sd_assets/cores3_assets/animations/encounter

  # 自定义尺寸 / 背景 / 体积上限
  python tools/convert_frames.py <src_dir> --out <dst_dir> ^
      --size 320x240 --bg 255,255,255 --max-kb 140

转好后把 sd_assets/cores3_assets/ 整个拷到 SD 卡根目录即可。
"""
import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("缺少依赖：请先运行  pip install pillow")
    sys.exit(1)


def parse_size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def parse_bg(s):
    parts = [int(x) for x in s.split(",")]
    return tuple(parts[:3])


def fit_letterbox(img, size, bg):
    """等比缩放后居中贴到 size 画布上（留白，不裁切）。像素画用 NEAREST 保边。"""
    tw, th = size
    img = img.convert("RGBA")
    iw, ih = img.size
    scale = min(tw / iw, th / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = img.resize((nw, nh), Image.NEAREST)
    canvas = Image.new("RGB", size, bg)
    canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2), resized)
    return canvas


def save_under_max(img, path, max_kb):
    """降质量直到 <= max_kb，返回最终大小(bytes)。"""
    for q in (92, 85, 78, 70, 62, 55, 48, 40):
        img.save(path, "JPEG", quality=q, optimize=True)
        if path.stat().st_size <= max_kb * 1024:
            return path.stat().st_size
    return path.stat().st_size


def main():
    ap = argparse.ArgumentParser(description="Convert PNG frames for M5 CoreS3")
    ap.add_argument("src", help="源目录（含 .png 帧）")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--size", default="320x240", help="目标尺寸，默认 320x240")
    ap.add_argument("--bg", default="255,255,255", help="留白背景 RGB，默认白色")
    ap.add_argument("--max-kb", type=int, default=140, help="单帧最大 KB，默认 140")
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    size = parse_size(args.size)
    bg = parse_bg(args.bg)

    if not src.is_dir():
        print("源目录不存在：%s" % src)
        sys.exit(1)

    frames = sorted(
        [p for p in src.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")],
        key=lambda p: p.name,
    )
    if not frames:
        print("源目录里没有图片：%s" % src)
        sys.exit(1)

    out.mkdir(parents=True, exist_ok=True)
    print("输入 %d 帧 -> %s  (尺寸 %dx%d, <= %dKB)"
          % (len(frames), out, size[0], size[1], args.max_kb))

    for i, fp in enumerate(frames, start=1):
        img = Image.open(fp)
        canvas = fit_letterbox(img, size, bg)
        dst = out / ("frame_%04d.jpg" % i)
        n = save_under_max(canvas, dst, args.max_kb)
        flag = "OK" if n <= args.max_kb * 1024 else "STILL BIG"
        print("  %12s -> %s  %dKB  [%s]" % (fp.name, dst.name, n // 1024, flag))

    print("完成。把输出目录所在的 cores3_assets/ 拷到 SD 卡根目录即可。")


if __name__ == "__main__":
    main()
