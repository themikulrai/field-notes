"""Managed media root: copy-in with dedup + missing-reference scan."""

from __future__ import annotations

import pytest
from field_notes_api import media

# --- add_media ------------------------------------------------------------


def test_add_media_copies_and_returns_relative_url(tmp_path):
    root = tmp_path / "media"
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"video-bytes")

    results = media.add_media([src], task="demo", media_root=root)

    assert results == [("/media/demo/clip.mp4", "copied")]
    assert (root / "demo" / "clip.mp4").read_bytes() == b"video-bytes"


def test_add_media_skips_byte_identical_file(tmp_path):
    root = tmp_path / "media"
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"same")

    media.add_media([src], task="demo", media_root=root)
    results = media.add_media([src], task="demo", media_root=root)

    assert results == [("/media/demo/clip.mp4", "skipped")]


def test_add_media_refuses_silent_overwrite_of_different_content(tmp_path):
    root = tmp_path / "media"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "clip.mp4").write_bytes(b"original")

    src = tmp_path / "clip.mp4"
    src.write_bytes(b"DIFFERENT")

    with pytest.raises(FileExistsError):
        media.add_media([src], task="demo", media_root=root)


# --- reference scanning ---------------------------------------------------


def test_collect_media_refs_finds_video_url_and_inline_paths():
    blob = '{"video": {"url": "/media/demo/a.mp4"}} see also /media/demo/b.png and https://x/c'
    refs = media.collect_media_refs(blob)
    assert "/media/demo/a.mp4" in refs
    assert "/media/demo/b.png" in refs
    # external URL is not a managed /media path
    assert not any("https://x" in r for r in refs)


def test_missing_media_reports_only_absent_managed_paths(tmp_path):
    root = tmp_path / "media"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "a.mp4").write_bytes(b"x")

    urls = [
        "/media/demo/a.mp4",  # present
        "/media/demo/b.mp4",  # missing
        "data:video/mp4;base64,AAAA",  # inline, ignore
        "https://cdn/c.mp4",  # external, ignore
    ]
    missing = media.missing_media(root, urls)
    assert missing == ["/media/demo/b.mp4"]


# --- CLI wiring -----------------------------------------------------------


def test_cli_add_media_copies_into_managed_root(tmp_path):
    from field_notes_api import cli

    src = tmp_path / "v.mp4"
    src.write_bytes(b"x")
    rc = cli.main(["add-media", str(src), "--task", "t", "--data-dir", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "media" / "t" / "v.mp4").is_file()


def test_cli_verify_media_flags_missing_reference(tmp_path):
    """Exercises the real cells-table column read against a minimal SQLite DB."""
    import sqlite3

    from field_notes_api import cli

    (tmp_path / "media").mkdir()
    db = tmp_path / "field-notes.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE cells (video TEXT, body TEXT, visual TEXT, deep TEXT)")
    con.execute(
        "INSERT INTO cells VALUES (?,?,?,?)",
        ('{"url":"/media/t/missing.mp4"}', None, None, None),
    )
    con.commit()
    con.close()

    rc = cli.main(["verify-media", "--data-dir", str(tmp_path)])
    assert rc == 1  # /media/t/missing.mp4 is referenced but absent
