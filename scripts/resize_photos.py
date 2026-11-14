#!/usr/bin/env python3
"""image_resizer.py - bulk resize and/or convert images in a folder with Pillow.

Your originals are NEVER touched unless you explicitly ask for in-place mode
(--overwrite without --out). By default results go to a "resized" subfolder.

Requires the Pillow library:
    pip install Pillow

Usage examples:
    python image_resizer.py C:/photos --max-width 1200
    python image_resizer.py C:/photos --max-width 1200 --format jpg --quality 85
    python image_resizer.py C:/photos --max-width 800 --out C:/web-images --overwrite

Exit codes: 0 = success (even with some skipped files), 1 = fatal error,
2 = wrong command line usage.
"""

import argparse
import sys
from pathlib import Path

PILImage = None

# Extensions Pillow can open in a typical install.
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

# Pillow save-format names for a given target extension.
FORMAT_BY_EXT = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
    ".bmp": "BMP", ".gif": "GIF", ".tif": "TIFF", ".tiff": "TIFF",
}


def _load_pillow():
    """Import Pillow, or exit with a friendly install hint."""
    global PILImage
    if PILImage is not None:
        return
    try:
        from PIL import Image
    except ImportError:
        print("Error: the 'Pillow' library is not installed.")
        print("Install it with:  pip install Pillow")
        sys.exit(1)
    PILImage = Image


def _positive_int(value):
    """argparse type: an integer greater than zero."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("'%s' is not a number" % value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive number (got %d)" % number)
    return number


def _quality_int(value):
    """argparse type: quality in the 1..100 range."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("'%s' is not a number" % value)
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("quality must be between 1 and 100 (got %d)" % number)
    return number


def compute_new_size(width, height, max_width, max_height):
    """Shrink to fit inside max_width x max_height, keeping the aspect ratio.

    Never enlarges: if the image is already smaller, the size is unchanged.
    Returns (new_width, new_height) as ints.
    """
    if not max_width and not max_height:
        return width, height
    scale = 1.0
    if max_width and width > max_width:
        scale = min(scale, max_width / float(width))
    if max_height and height > max_height:
        scale = min(scale, max_height / float(height))
    if scale >= 1.0:
        return width, height
    return max(1, int(width * scale)), max(1, int(height * scale))


def process_image(src_path, out_path, args):
    """Resize/convert one image. Returns a short status string."""
    ext = args.format.lower() if args.format else src_path.suffix.lower()
    if not ext.startswith("."):
        ext = "." + ext
    if ext in (".jpg", ".jpeg"):
        save_format = "JPEG"
        save_ext = ".jpg"
    elif ext == ".webp":
        save_format = "WEBP"
        save_ext = ".webp"
    elif ext == ".png":
        save_format = "PNG"
        save_ext = ".png"
    else:
        save_format = FORMAT_BY_EXT.get(ext)
        save_ext = ext
    if save_format is None:
        return None  # unsupported target format, caller reports a skip

    target = out_path.with_suffix(save_ext)
    with PILImage.open(src_path) as img:
        width, height = img.size
        new_w, new_h = compute_new_size(width, height, args.max_width, args.max_height)
        if new_w != width or new_h != height:
            img = img.resize((new_w, new_h), PILImage.LANCZOS)

        # JPEG has no alpha channel; flatten transparency onto white.
        if save_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = PILImage.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background

        # Force full decode now: when saving in place we are about to
        # overwrite the very file Pillow reads from.
        img.load()
        save_kwargs = {}
        if save_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = args.quality
        try:
            img.save(str(target), save_format, **save_kwargs)
        except PermissionError:
            return "error:%s is locked (open in another program?)" % target
    if new_w == width and new_h == height and save_ext == src_path.suffix.lower():
        return "copied:%s (no resize needed)" % target
    return "ok:%s -> %dx%d" % (target, new_w, new_h)


def main():
    parser = argparse.ArgumentParser(
        prog="image_resizer.py",
        description="Bulk resize and/or convert images in a folder. "
                    "Originals are never modified unless you use --overwrite "
                    "without --out (in-place mode).",
        epilog="Examples:\n"
               "  python image_resizer.py C:/photos --max-width 1200\n"
               "  python image_resizer.py C:/photos --max-width 1200 --format jpg\n"
               "  python image_resizer.py C:/photos --max-width 800 --out C:/web --overwrite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("folder", help="folder containing the images")
    parser.add_argument("--max-width", type=_positive_int,
                        help="shrink images wider than this; aspect ratio is kept")
    parser.add_argument("--max-height", type=_positive_int,
                        help="shrink images taller than this; aspect ratio is kept")
    parser.add_argument("--format", choices=["png", "jpg", "webp"],
                        help="convert images to this format (default: keep each original)")
    parser.add_argument("--quality", type=_quality_int, default=85,
                        help="quality for jpg/webp, 1-100 (default: 85)")
    parser.add_argument("--out", help="output folder (default: <folder>\\resized)")
    parser.add_argument("--overwrite", action="store_true",
                        help="overwrite existing results; without --out this also "
                             "modifies the originals in place")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not folder.is_dir():
        print("Error: folder not found: %s" % folder)
        sys.exit(1)

    if not args.max_width and not args.max_height and not args.format:
        print("Error: nothing to do. Give at least one of --max-width, --max-height, --format.")
        print('Example: python image_resizer.py "%s" --max-width 1200' % folder)
        sys.exit(2)

    # In-place mode: --overwrite without --out. Otherwise use a result folder.
    in_place = args.overwrite and not args.out
    if in_place:
        out_dir = folder
    else:
        out_dir = Path(args.out) if args.out else folder / "resized"

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        print("Error: cannot create output folder '%s' (no permission?)" % out_dir)
        sys.exit(1)

    files = sorted(p for p in folder.iterdir() if p.is_file())
    if not files:
        print("No files found in %s." % folder)
        return  # nothing to do is not an error

    _load_pillow()

    done, skipped, failed = 0, 0, 0
    for src_path in files:
        if src_path.suffix.lower() not in IMAGE_EXTS:
            skipped += 1
            print("Skipped %s (not an image)" % src_path.name)
            continue
        if in_place:
            target_path = src_path
        else:
            target_path = out_dir / src_path.name
            if target_path.exists() and not args.overwrite:
                skipped += 1
                print("Skipped %s (already exists in %s, use --overwrite to replace)"
                      % (target_path.name, out_dir))
                continue
        status = process_image(src_path, target_path, args)
        if status is None:
            skipped += 1
            print("Skipped %s (cannot save as %s format)" % (src_path.name, args.format))
        elif status.startswith("error:"):
            failed += 1
            print("Error: %s" % status[len("error:"):])
        else:
            done += 1
            if status.startswith("ok:"):
                status = status[len("ok:"):]
            elif status.startswith("copied:"):
                status = status[len("copied:"):]
            print("Resized %s" % status)

    print("")
    print("Summary: %d processed, %d skipped, %d failed." % (done, skipped, failed))
    if in_place:
        print("Note: originals were modified in place (you used --overwrite).")
    else:
        print("Results are in: %s" % out_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
