#!/usr/bin/env python3
"""
递归缩小动画帧，让 M5 CoreS3 能流畅播放。

背景：板子每帧要把整张图读进内存再解码。实测张总(zhang_zong)的帧
每张约 950KB，远超流畅播放所需（小红的帧才 ~65KB），会把主循环和
BLE 扫描都拖慢。本脚本把每张图等比缩放居中铺到 320x240（屏幕分辨率，
不裁切），并压到目标体积以下；**保留原文件名与扩展名、保留子目录结构**，
所以适合直接对着 SD 卡上的 `<persona>/animations/` 整个目录跑。

依赖：pip install pillow （anaconda 自带）

默认是**非破坏性**的：输出到 `<目标>_small/`，结构同源，你确认没问题
再把它替换回卡上对应目录。想直接就地覆盖加 --inplace（会先备份到
`<目标>_backup/`）。

用法：
  # 非破坏：缩小卡上张总所有状态的帧到 E:\\zhang_zong_small\\
  python tools/shrink_frames.py E:\\zhang_zong\\animations

  # 就地覆盖（自动先备份）
  python tools/shrink_frames.py E:\\zhang_zong\\animations --inplace

  # 自定义尺寸/体积/背景
  python tools/shrink_frames.py <dir> --size 320x240 --max-kb 120 --bg 255,255,255
"""
import argparse
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("缺少依赖：请先运行  pip install pillow")
    sys.exit(1)

IMG_EXT = (".png", ".jpg", ".jpeg")


def parse_size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


def parse_bg(s):
    parts = [int(x) for x in s.split(",")]
    return tuple(parts[:3])


def fit_letterbox(img, size, bg):
    """等比缩放后居中贴到 size 画布（留白，不裁切）。像素画用 NEAREST 保边。"""
    tw, th = size
    img = img.convert("RGBA")
    iw, ih = img.size
    scale = min(tw / iw, th / ih)
    # 只缩不放：若原图已小于画布则保持原尺寸居中
    if scale > 1.0:
        scale = 1.0
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = img.resize((nw, nh), Image.NEAREST)
    canvas = Image.new("RGB", size, bg)
    canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2), resized)
    return canvas


def save_png_under_max(img, path, max_kb):
    """PNG 优化保存；若仍超限，逐步减色(量化)直到达标。返回最终字节数。"""
    img.save(path, "PNG", optimize=True)
    if path.stat().st_size <= max_kb * 1024:
        return path.stat().st_size
    for colors in (256, 128, 64, 32):
        q = img.convert("P", palette=Image.ADAPTIVE, colors=colors)
        q.save(path, "PNG", optimize=True)
        if path.stat().st_size <= max_kb * 1024:
            return path.stat().st_size
    return path.stat().st_size


def save_jpg_under_max(img, path, max_kb):
    """JPG 逐步降质直到达标。返回最终字节数。"""
    for quality in (92, 85, 78, 70, 62, 55, 48, 40):
        img.save(path, "JPEG", quality=quality, optimize=True)
        if path.stat().st_size <= max_kb * 1024:
            return path.stat().st_size
    return path.stat().st_size


def main():
    ap = argparse.ArgumentParser(description="递归缩小 M5 动画帧（保留名字与目录结构）")
    ap.add_argument("src", help="源目录（会递归处理其下所有图片）")
    ap.add_argument("--size", default="320x240", help="目标画布尺寸，默认 320x240")
    ap.add_argument("--bg", default="255,255,255", help="留白背景 RGB，默认白色")
    ap.add_argument("--max-kb", type=int, default=120, help="单帧最大 KB，默认 120")
    ap.add_argument("--inplace", action="store_true", help="就地覆盖（先备份到 <src>_backup）")
    args = ap.parse_args()

    src = Path(args.src)
    size = parse_size(args.size)
    bg = parse_bg(args.bg)

    if not src.is_dir():
        print("源目录不存在：%s" % src)
        sys.exit(1)

    images = sorted(p for p in src.rglob("*") if p.suffix.lower() in IMG_EXT)
    if not images:
        print("目录里没有图片：%s" % src)
        sys.exit(1)

    if args.inplace:
        backup = src.parent / (src.name + "_backup")
        if not backup.exists():
            print("备份原始目录 -> %s" % backup)
            shutil.copytree(src, backup)
        out_root = src
    else:
        out_root = src.parent / (src.name + "_small")
        out_root.mkdir(parents=True, exist_ok=True)

    print("处理 %d 张图  ->  %s  (<=%dKB, %dx%d)"
          % (len(images), out_root, args.max_kb, size[0], size[1]))

    total_before = total_after = 0
    for fp in images:
        before = fp.stat().st_size
        total_before += before
        rel = fp.relative_to(src)
        dst = out_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        img = Image.open(fp)
        canvas = fit_letterbox(img, size, bg)
        if fp.suffix.lower() == ".png":
            after = save_png_under_max(canvas, dst, args.max_kb)
        else:
            after = save_jpg_under_max(canvas, dst, args.max_kb)
        total_after += after
        flag = "OK" if after <= args.max_kb * 1024 else "STILL BIG"
        print("  %-40s %5dKB -> %4dKB  [%s]"
              % (str(rel), before // 1024, after // 1024, flag))

    print("完成。总计 %dKB -> %dKB（约 1/%d）。"
          % (total_before // 1024, total_after // 1024,
             max(1, total_before // max(1, total_after))))
    if not args.inplace:
        print("确认无误后，把 %s 的内容替换回卡上对应目录即可。" % out_root)


if __name__ == "__main__":
    main()
