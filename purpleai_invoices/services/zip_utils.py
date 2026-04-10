# -*- coding: utf-8 -*-

import os
import zipfile
import shutil


class ZipSecurityError(Exception):
    """Raised when ZIP file is unsafe to extract"""
    pass


def _is_symlink_zipinfo(info: zipfile.ZipInfo) -> bool:
    """
    Best-effort symlink detection for UNIX zips.
    """
    try:
        # external_attr high 16 bits are UNIX permissions + file type
        mode = (info.external_attr >> 16) & 0xFFFF
        # symlink bit: 0o120000
        return (mode & 0o170000) == 0o120000
    except Exception:
        return False


def safe_extract_zip(
    zip_path: str,
    extract_dir: str,
    max_files: int = 2000,
    max_total_uncompressed_bytes: int = 500 * 1024 * 1024,  # 500MB
) -> None:
    """
    Safely extract a zip:
      - blocks path traversal (../)
      - blocks absolute paths
      - blocks symlinks
      - limits file count and total uncompressed bytes

    Raises ZipSecurityError for unsafe zips.
    """
    os.makedirs(extract_dir, exist_ok=True)

    extract_root = os.path.abspath(extract_dir)

    total = 0
    count = 0

    with zipfile.ZipFile(zip_path, "r") as z:
        infos = z.infolist()

        # 1) Validate everything first
        for info in infos:
            count += 1
            if count > max_files:
                raise ZipSecurityError("ZIP contains too many files")

            # total uncompressed size estimate
            total += int(getattr(info, "file_size", 0) or 0)
            if total > max_total_uncompressed_bytes:
                raise ZipSecurityError("ZIP is too large to extract (zip-bomb protection)")

            name = info.filename or ""

            # Block absolute paths
            if name.startswith("/") or name.startswith("\\"):
                raise ZipSecurityError("ZIP contains absolute paths (blocked)")

            # Block symlinks
            if _is_symlink_zipinfo(info):
                raise ZipSecurityError("ZIP contains symlink entries (blocked)")

            # Normalize and block traversal (absolute compare)
            normalized = os.path.normpath(name).lstrip("\\/")  # remove leading separators
            target_path = os.path.abspath(os.path.join(extract_root, normalized))

            # Must stay inside extract_root
            if not (target_path == extract_root or target_path.startswith(extract_root + os.sep)):
                raise ZipSecurityError("ZIP path traversal detected (blocked)")

        # 2) Extract safely (manual write)
        for info in infos:
            name = info.filename or ""
            normalized = os.path.normpath(name).lstrip("\\/")
            target_path = os.path.abspath(os.path.join(extract_root, normalized))

            # Directory entry
            if name.endswith("/") or name.endswith("\\") or info.is_dir():
                os.makedirs(target_path, exist_ok=True)
                continue

            parent = os.path.dirname(target_path)
            os.makedirs(parent, exist_ok=True)

            # Stream write file
            with z.open(info, "r") as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
