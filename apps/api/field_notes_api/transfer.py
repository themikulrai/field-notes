"""Fetch the baked media tarballs into the local media root.

`fetch_media` pulls the media tarballs (URLs declared in the Dockerfile) into the
managed media root so `/media/...` references resolve locally.
"""

from __future__ import annotations

import re
import tarfile
import tempfile
import urllib.request
from pathlib import Path

_TARBALL_URL = re.compile(r"https://\S+?\.tar\.gz")


def parse_media_urls(dockerfile_text: str) -> list[str]:
    """Return the media tarball URLs declared in the Dockerfile, de-duplicated
    in first-seen order."""
    seen: dict[str, None] = {}
    for url in _TARBALL_URL.findall(dockerfile_text):
        seen.setdefault(url, None)
    return list(seen)


def fetch_media(media_root: Path, urls: list[str]) -> list[str]:
    """Download + extract each tarball into media_root. Returns the URLs fetched.

    Uses tarfile's `data` filter to reject path-traversal / absolute members.
    """
    root = Path(media_root)
    root.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for url in urls:
        with tempfile.NamedTemporaryFile(suffix=".tar.gz") as tmp:
            urllib.request.urlretrieve(url, tmp.name)  # noqa: S310 — fixed https HF URLs
            with tarfile.open(tmp.name, "r:gz") as tar:
                tar.extractall(root, filter="data")
        fetched.append(url)
    return fetched
