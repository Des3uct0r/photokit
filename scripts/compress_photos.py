#!/usr/bin/env python3
"""compress_photos.py - shrink JPEG/PNG file sizes without changing dimensions.

Re-encodes images at a lower quality / optimized palette. Originals untouched;
results go to a "compressed" subfolder unless --overwrite is used.

Usage:
    python compress_photos.py C:/photos
    python compress_photos.py C:/photos --quality 70
    python compress_photos.py C:/photos --out C:/small --overwrite

Requires Pillow: pip install Pillow
"""
import argparse, sys
from pathlib import Path

PILImage = None
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

def load_pillow():
    global PILImage
    if PILImage is not None:
        return
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow is not installed. Run: pip install Pillow")
        sys.exit(1)
    PILImage = Image

def main():
    ap = argparse.ArgumentParser(description="Compress images to smaller files.")
    ap.add_argument("folder", help="folder with images")
    ap.add_argument("--quality", type=int, default=75, help="JPEG/WebP quality 1-95 (default 75)")
    ap.add_argument("--out", help="output folder (default: <folder>/compressed)")
    ap.add_argument("--overwrite", action="store_true", help="overwrite existing results")
    args = ap.parse_args()

    folder = Path(args.folder)
    if not folder.is_dir():
        print("Error: folder not found: %s" % folder); sys.exit(1)
    out = Path(args.out) if args.out else folder / "compressed"
    out.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    if not files:
        print("No images found."); return
    load_pillow()
    done = skipped = failed = 0
    for src in files:
        dst = (folder / src.name) if (args.overwrite and not args.out) else (out / src.name)
        if dst.exists() and not args.overwrite and not args.out:
            skipped += 1; print("Skipped %s (exists)" % src.name); continue
        try:
            with PILImage.open(src) as img:
                img.load()
                fmt = "JPEG" if src.suffix.lower() in (".jpg", ".jpeg") else ("PNG" if src.suffix.lower() == ".png" else "WEBP")
                if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                save_kw = {}
                if fmt in ("JPEG", "WEBP"):
                    save_kw["quality"] = args.quality
                    save_kw["optimize"] = True
                if fmt == "PNG":
                    save_kw["optimize"] = True
                img.save(str(dst), fmt, **save_kw)
            before = src.stat().st_size
            after = dst.stat().st_size
            pct = (1 - after / before) * 100 if before else 0
            done += 1
            print("Compressed %s: %d KB -> %d KB (%.0f%% smaller)" % (src.name, before // 1024, after // 1024, pct))
        except Exception as e:
            failed += 1; print("Error on %s: %s" % (src.name, e))
    print("\nSummary: %d compressed, %d skipped, %d failed." % (done, skipped, failed))
    if not (args.overwrite and not args.out):
        print("Results are in: %s" % out)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled."); sys.exit(130)
