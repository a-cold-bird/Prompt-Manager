#!/usr/bin/env python3
"""
Repair thumbnails for Prompt Manager images.

Typical usage:
  python scripts/repair_thumbnails.py --dry-run
  python scripts/repair_thumbnails.py --status approved
  python scripts/repair_thumbnails.py --status approved --force
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable

from PIL import Image as PilImage

# Ensure project root is importable when running script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from extensions import db
from models import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair missing/invalid thumbnail_path records.")
    parser.add_argument(
        "--status",
        default="approved",
        help="Filter by image status. Use '*' to process all statuses. Default: approved",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated image IDs to process (optional).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of images to process (0 means no limit).",
    )
    parser.add_argument(
        "--thumb-size",
        type=int,
        default=400,
        help="Thumbnail max width/height in px. Default: 400",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=88,
        help="JPEG quality (1-100). Default: 88",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate thumbnail even if existing thumbnail_path looks valid.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would change, do not write files or DB.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-image details.",
    )
    return parser.parse_args()


def normalize_web_path(path: str | None) -> str:
    if not path:
        return ""
    path = str(path).strip().replace("\\", "/")
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return path


def is_remote_path(path: str) -> bool:
    return path.startswith(("http://", "https://"))


def build_thumb_web_path(source_web_path: str) -> str:
    rel = source_web_path.lstrip("/")
    posix = PurePosixPath(rel)
    thumb_name = f"{posix.stem}_thumb.jpg"
    return "/" + str(posix.with_name(thumb_name))


def web_to_abs(app_root: str, web_path: str) -> str:
    return os.path.join(app_root, web_path.lstrip("/"))


def parse_ids(raw_ids: str) -> list[int]:
    if not raw_ids.strip():
        return []
    ids: list[int] = []
    for part in raw_ids.split(","):
        part = part.strip()
        if not part:
            continue
        ids.append(int(part))
    return ids


def save_thumbnail(source_abs: str, thumb_abs: str, thumb_size: int, quality: int) -> None:
    os.makedirs(os.path.dirname(thumb_abs), exist_ok=True)

    with PilImage.open(source_abs) as im:
        # For animated formats (e.g. GIF), use first frame.
        if getattr(im, "is_animated", False):
            im.seek(0)

        if im.mode not in ("RGB",):
            im = im.convert("RGB")

        thumb = im.copy()
        thumb.thumbnail((thumb_size, thumb_size), PilImage.Resampling.LANCZOS)
        thumb.save(thumb_abs, format="JPEG", quality=quality, optimize=True)
        thumb.close()


def iter_target_images(args: argparse.Namespace) -> Iterable[Image]:
    query = Image.query

    if args.status != "*":
        query = query.filter_by(status=args.status)

    ids = parse_ids(args.ids)
    if ids:
        query = query.filter(Image.id.in_(ids))

    query = query.order_by(Image.id.asc())

    if args.limit and args.limit > 0:
        query = query.limit(args.limit)

    return query.all()


def main() -> None:
    args = parse_args()

    if args.quality < 1 or args.quality > 100:
        raise ValueError("--quality must be between 1 and 100")
    if args.thumb_size < 32:
        raise ValueError("--thumb-size must be >= 32")

    app = create_app()

    scanned = 0
    updated = 0
    unchanged = 0
    missing_source = 0
    remote_skipped = 0
    errors = 0

    with app.app_context():
        images = iter_target_images(args)
        print(f"Loaded {len(images)} images for scan.")

        for img in images:
            scanned += 1
            try:
                src_web = normalize_web_path(img.file_path)
                if not src_web:
                    errors += 1
                    if args.verbose:
                        print(f"[ERR] #{img.id}: empty file_path")
                    continue

                if is_remote_path(src_web):
                    remote_skipped += 1
                    if args.verbose:
                        print(f"[SKIP] #{img.id}: remote source ({src_web})")
                    continue

                src_abs = web_to_abs(app.root_path, src_web)
                if not os.path.exists(src_abs):
                    missing_source += 1
                    if args.verbose:
                        print(f"[MISS] #{img.id}: source missing -> {src_abs}")
                    continue

                current_thumb_web = normalize_web_path(img.thumbnail_path)
                current_thumb_abs = (
                    web_to_abs(app.root_path, current_thumb_web)
                    if current_thumb_web and not is_remote_path(current_thumb_web)
                    else ""
                )

                need_repair = False
                if args.force:
                    need_repair = True
                elif not current_thumb_web:
                    need_repair = True
                elif current_thumb_web == src_web:
                    need_repair = True
                elif is_remote_path(current_thumb_web):
                    need_repair = False
                elif not os.path.exists(current_thumb_abs):
                    need_repair = True

                if not need_repair:
                    unchanged += 1
                    if args.verbose:
                        print(f"[OK] #{img.id}: keep {current_thumb_web}")
                    continue

                new_thumb_web = build_thumb_web_path(src_web)
                new_thumb_abs = web_to_abs(app.root_path, new_thumb_web)

                if args.dry_run:
                    updated += 1
                    if args.verbose:
                        print(f"[DRY] #{img.id}: {current_thumb_web or '<empty>'} -> {new_thumb_web}")
                    continue

                save_thumbnail(
                    source_abs=src_abs,
                    thumb_abs=new_thumb_abs,
                    thumb_size=args.thumb_size,
                    quality=args.quality,
                )
                img.thumbnail_path = new_thumb_web
                updated += 1
                if args.verbose:
                    print(f"[FIX] #{img.id}: {current_thumb_web or '<empty>'} -> {new_thumb_web}")
            except Exception as exc:  # noqa: BLE001
                errors += 1
                if args.verbose:
                    print(f"[ERR] #{img.id}: {exc}")

        if not args.dry_run and updated > 0:
            db.session.commit()

    print("")
    print("Thumbnail repair summary:")
    print(f"  scanned:        {scanned}")
    print(f"  updated:        {updated}{' (dry-run)' if args.dry_run else ''}")
    print(f"  unchanged:      {unchanged}")
    print(f"  missing_source: {missing_source}")
    print(f"  remote_skipped: {remote_skipped}")
    print(f"  errors:         {errors}")


if __name__ == "__main__":
    main()
