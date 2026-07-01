"""Media tarball URL parsing for the `fetch-media` command."""

from __future__ import annotations

from field_notes_api import transfer


def test_parse_media_urls_from_dockerfile():
    text = (
        "ARG LIFTBARRIER_MEDIA_URL=https://huggingface.co/datasets/x/resolve/main/liftbarrier_media.tar.gz\n"
        'RUN curl -fsSL "$LIFTBARRIER_MEDIA_URL" | tar -xz -C /repo/apps/api/media\n'
        "ARG MEMER_MEDIA_URL=https://huggingface.co/datasets/x/resolve/main/memer_media.tar.gz\n"
    )
    urls = transfer.parse_media_urls(text)
    assert urls == [
        "https://huggingface.co/datasets/x/resolve/main/liftbarrier_media.tar.gz",
        "https://huggingface.co/datasets/x/resolve/main/memer_media.tar.gz",
    ]


def test_parse_media_urls_dedupes_first_seen():
    text = "ARG A=https://h/x.tar.gz\nARG B=https://h/y.tar.gz\nARG A2=https://h/x.tar.gz\n"
    assert transfer.parse_media_urls(text) == ["https://h/x.tar.gz", "https://h/y.tar.gz"]
