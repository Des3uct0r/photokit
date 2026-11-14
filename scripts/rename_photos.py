#!/usr/bin/env python3
"""bulk_rename.py - Rename many files in a folder at once, safely.

The default behavior is a DRY RUN: it only SHOWS what would happen.
Nothing is renamed until you add --apply.

Usage examples:
    python bulk_rename.py C:/photos --number
    python bulk_rename.py C:/photos --ext-filter .jpg --lower --apply
    python bulk_rename.py C:/docs --replace 2023_ 2024_ --prefix scan_
    python bulk_rename.py C:/photos --suffix _final --ext-filter .png

Modes (can be combined, applied in this order):
    --replace OLD NEW   replace the first occurrence of OLD in each name
    --prefix TEXT       add TEXT in front of the file name
    --suffix TEXT       add TEXT before the extension (keeps extension)
    --lower             make the whole name lowercase
    --upper             make the whole name uppercase
    --number            rename to 001, 002, 003 ... keeping the extension
    --ext-filter .jpg   only touch files ending in .jpg (repeatable)

Safety rules:
    - Subfolders are never touched, and this script is never recursive.
    - Files are only renamed with --apply; otherwise you just see the plan.
    - A rename that would overwrite an existing file is skipped with a note.
"""

import argparse
import sys
from pathlib import Path


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Rename files in a folder by pattern (dry-run by default).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("folder", help="Folder containing the files to rename.")
    parser.add_argument("--replace", nargs=2, metavar=("OLD", "NEW"),
                        help="Replace OLD with NEW in the file name (first occurrence).")
    parser.add_argument("--prefix", metavar="TEXT", help="Text to add in front of each name.")
    parser.add_argument("--suffix", metavar="TEXT", help="Text to add before the extension.")
    parser.add_argument("--lower", action="store_true", help="Make names lowercase.")
    parser.add_argument("--upper", action="store_true", help="Make names uppercase.")
    parser.add_argument("--number", action="store_true",
                        help="Rename to 001, 002, ... keeping the extension.")
    parser.add_argument("--ext-filter", action="append", default=[], metavar="EXT",
                        help="Only rename files with this extension, e.g. .jpg (repeatable).")
    parser.add_argument("--apply", action="store_true",
                        help="Actually rename the files (default: dry run only).")
    return parser


def normalize_extensions(ext_list):
    """Return extensions as lowercase dotted strings, e.g. '.jpg'."""
    result = []
    for ext in ext_list:
        ext = ext.lower().strip()
        if not ext.startswith("."):
            ext = "." + ext
        result.append(ext)
    return result


def pick_files(folder, ext_filters):
    """Return files directly inside the folder (no subfolders, never recursive)."""
    try:
        entries = sorted(folder.iterdir())
    except OSError as exc:
        print("ERROR: cannot read folder '%s': %s" % (folder, exc))
        sys.exit(2)

    files = [p for p in entries if p.is_file()]
    if ext_filters:
        files = [p for p in files if p.suffix.lower() in ext_filters]
    return files


def new_name_for(path, args, index):
    """Compute the new file name for one path, or None if it stays the same."""
    suffix = path.suffix          # includes the dot, e.g. ".jpg"
    stem = path.stem              # name without extension

    if args.number:
        # 001, 002 ... with enough zero padding for the total file count.
        name = str(index + 1).zfill(3)
        return name + suffix

    if args.replace:
        old, new = args.replace
        stem = stem.replace(old, new, 1)

    if args.prefix:
        stem = args.prefix + stem

    if args.suffix:
        stem = stem + args.suffix

    name = stem + suffix

    if args.lower:
        name = name.lower()
    if args.upper:
        name = name.upper()

    if name == path.name:
        return None
    return name


def main():
    args = build_arg_parser().parse_args()

    if not any([args.replace, args.prefix, args.suffix, args.lower,
                args.upper, args.number]):
        print("ERROR: pick at least one mode, e.g. --number, --prefix, --replace OLD NEW.")
        print("Run 'python bulk_rename.py --help' to see all modes.")
        sys.exit(2)

    folder = Path(args.folder)
    if not folder.is_dir():
        print("ERROR: '%s' is not a folder (check the spelling and location)." % folder)
        sys.exit(2)

    ext_filters = normalize_extensions(args.ext_filter)
    files = pick_files(folder, ext_filters)

    if not files:
        msg = "No files found in '%s'" % folder
        if ext_filters:
            msg += " matching extension(s) %s" % ", ".join(ext_filters)
        print(msg + ". Nothing to do.")
        sys.exit(0)

    # Build the plan: list of (old_path, new_name).
    plan = []
    skipped_no_change = 0
    for index, path in enumerate(files):
        new_name = new_name_for(path, args, index)
        if new_name is None:
            skipped_no_change += 1
            continue
        plan.append((path, new_name))

    print("Folder: %s" % folder)
    print("Files considered: %d" % len(files))
    if skipped_no_change:
        print("Files already matching (no change needed): %d" % skipped_no_change)
    print("Planned renames: %d" % len(plan))
    print("Mode: %s" % ("APPLY (files will be renamed)" if args.apply
                       else "DRY RUN (nothing renamed yet; add --apply to rename)"))
    print("-" * 60)

    # Detect duplicate target names (e.g. two files lowercased to the same name).
    seen_targets = {}
    problems = 0
    done = 0

    for old_path, new_name in plan:
        target = old_path.with_name(new_name)
        note = ""
        would_conflict = False

        if new_name in seen_targets:
            note = "SKIP: another file is also renamed to '%s'" % new_name
            would_conflict = True
        seen_targets[new_name] = old_path.name

        if not would_conflict and target.exists() and target != old_path:
            note = "SKIP: a file named '%s' already exists" % new_name
            would_conflict = True

        if would_conflict:
            problems += 1
            print("%-40s -> %-40s [%s]" % (old_path.name, new_name, note))
            continue

        print("%-40s -> %s" % (old_path.name, new_name))
        if args.apply:
            try:
                old_path.rename(target)
                done += 1
            except OSError as exc:
                problems += 1
                print("  ERROR renaming '%s': %s" % (old_path.name, exc))

    print("-" * 60)
    if args.apply:
        print("Done: %d renamed, %d skipped/failed." % (done, problems))
    else:
        print("Dry run finished. Nothing was changed.")
        print("Happy with the plan? Run the same command again with --apply.")


if __name__ == "__main__":
    main()
