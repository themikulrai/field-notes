"""Managed media root helpers for the local self-host.

Cells reference media by relative `/media/<task>/<file>` URLs (the API mounts
FIELD_NOTES_MEDIA_DIR at /media). `add_media` copies files into that root with
byte-hash dedup; `missing_media` reports referenced paths the root lacks so a
post-transition check surfaces gaps instead of silent blank cells.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Iterable
from pathlib import Path

# Managed media paths only; data: URIs are inline and external http(s) URLs are
# not ours to fetch, so both are ignored by the scan.
_MEDIA_REF = re.compile(r"/media/[A-Za-z0-9._\-/]+")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def add_media(files: Iterable[Path], *, task: str, media_root: Path) -> list[tuple[str, str]]:
    """Copy each file into `media_root/<task>/` and return (url, status) pairs.

    status: "copied" (new), "skipped" (byte-identical already there). A name
    collision with *different* bytes raises FileExistsError rather than silently
    clobbering — the caller renames instead of losing data.
    """
    dest_dir = Path(media_root) / task
    dest_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str]] = []
    for src in files:
        src = Path(src)
        dest = dest_dir / src.name
        url = f"/media/{task}/{src.name}"
        if dest.exists():
            if _sha256(dest) == _sha256(src):
                results.append((url, "skipped"))
                continue
            raise FileExistsError(
                f"{dest} already exists with different content; rename {src.name} to avoid overwriting"
            )
        shutil.copy2(src, dest)
        results.append((url, "copied"))
    return results


def collect_media_refs(blob: str) -> set[str]:
    """Return every managed `/media/...` reference found in a text blob (a cell's
    serialized video/body/visual/deep fields)."""
    return set(_MEDIA_REF.findall(blob))


def missing_media(media_root: Path, urls: Iterable[str]) -> list[str]:
    """Return the sorted managed `/media/...` URLs that have no file under
    media_root. data: and external URLs are ignored."""
    root = Path(media_root)
    missing: set[str] = set()
    for url in urls:
        if not url or not url.startswith("/media/"):
            continue
        rel = url[len("/media/") :]
        if not (root / rel).is_file():
            missing.add(url)
    return sorted(missing)
