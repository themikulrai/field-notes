"""`field-notes` command-line interface for the local single-process self-host.

Subcommands:
  serve         run migrations on a file-backed SQLite DB and start the server
  add-media     copy media files into the managed media root (see media.py)
  verify-media  report cell media URLs missing from the media root (see media.py)
  import-db     copy a remote DB (e.g. Heroku Postgres) into local SQLite (transfer.py)
  fetch-media   download the baked media tarballs into the media root (transfer.py)
  info          print the resolved local paths + auth mode

The pure helpers (`_is_loopback`, `build_serve_env`, `run_migrations`) are kept
side-effect-free so they can be unit-tested without binding a socket.
"""

from __future__ import annotations

import argparse
import contextlib
import os
from collections.abc import Mapping
from pathlib import Path

from .config import get_settings

DEFAULT_DATA_DIR = "~/.field-notes"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"}


def _is_loopback(host: str) -> bool:
    return host.strip("[]").lower() in _LOOPBACK_HOSTS


def build_serve_env(
    *,
    data_dir: Path,
    host: str,
    key: str | None = None,
    static_dir: str | None = None,
    existing: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Compute the env vars `serve` should set, honouring power-user overrides.

    Path vars (DATABASE_URL / media / data dir / static) are only filled when
    absent from `existing`, so e.g. `DATABASE_URL=postgres://…` still wins.

    Auth: an explicit `key` enables key auth; otherwise a loopback bind disables
    auth (local single-user); a public bind without a key is refused.
    """
    existing = existing or {}
    data_dir = Path(data_dir)
    env: dict[str, str] = {}

    if "DATABASE_URL" not in existing:
        env["DATABASE_URL"] = f"sqlite+aiosqlite:///{data_dir / 'field-notes.db'}"
    if "FIELD_NOTES_MEDIA_DIR" not in existing:
        env["FIELD_NOTES_MEDIA_DIR"] = str(data_dir / "media")
    if "FIELD_NOTES_DATA_DIR" not in existing:
        env["FIELD_NOTES_DATA_DIR"] = str(data_dir)
    if static_dir and "FIELD_NOTES_STATIC_DIR" not in existing:
        env["FIELD_NOTES_STATIC_DIR"] = str(static_dir)

    if key:
        env["FIELD_NOTES_KEY"] = key
    elif _is_loopback(host):
        env["FIELD_NOTES_AUTH_DISABLED"] = "1"
    else:
        raise ValueError(
            f"refusing to bind {host} without a key — pass --key to require auth, "
            "or bind a loopback host (127.0.0.1) for a private local notebook"
        )
    return env


def _find_alembic() -> tuple[Path, Path]:
    """Return (alembic.ini, script_location). Works from the source tree and
    from a wheel where the migrations are bundled under the package as _alembic/."""
    pkg = Path(__file__).resolve().parent
    candidates = [
        (pkg / "_alembic" / "alembic.ini", pkg / "_alembic" / "alembic"),  # packaged
        (pkg.parent / "alembic.ini", pkg.parent / "alembic"),  # source: apps/api/
    ]
    for ini, script in candidates:
        if ini.is_file() and script.is_dir():
            return ini, script
    raise FileNotFoundError("could not locate Alembic migrations (alembic.ini + alembic/)")


def run_migrations(database_url: str) -> None:
    """Run `alembic upgrade head` in-process. `env.py` normalises the URL to a
    sync driver (sqlite+aiosqlite → sqlite, postgres+asyncpg → postgresql)."""
    from alembic import command
    from alembic.config import Config

    ini, script_location = _find_alembic()
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(script_location))
    os.environ["DATABASE_URL"] = database_url
    command.upgrade(cfg, "head")


def resolve_static_dir() -> str | None:
    """Locate the built SPA: an explicit FIELD_NOTES_STATIC_DIR, else the
    packaged _web/ dir if it shipped with the wheel."""
    explicit = os.environ.get("FIELD_NOTES_STATIC_DIR")
    if explicit:
        return explicit
    packaged = Path(__file__).resolve().parent / "_web"
    if (packaged / "index.html").is_file():
        return str(packaged)
    return None


def _cmd_serve(args: argparse.Namespace) -> int:
    import webbrowser

    import uvicorn

    data_dir = Path(args.data_dir).expanduser()
    (data_dir / "media").mkdir(parents=True, exist_ok=True)

    env = build_serve_env(
        data_dir=data_dir,
        host=args.host,
        key=args.key,
        static_dir=resolve_static_dir(),
        existing=dict(os.environ),
    )
    os.environ.update(env)
    get_settings.cache_clear()

    run_migrations(os.environ["DATABASE_URL"])

    auth_mode = "DISABLED (local, loopback)" if env.get("FIELD_NOTES_AUTH_DISABLED") else "key required"
    url = f"http://{args.host}:{args.port}"
    print(f"field-notes: data dir {data_dir}")
    print(f"field-notes: auth {auth_mode}")
    print(f"field-notes: serving at {url}")

    if not args.no_browser:
        # Headless boxes have no browser; never let that abort serving.
        with contextlib.suppress(Exception):
            webbrowser.open(url)

    from .main import app

    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _cmd_add_media(args: argparse.Namespace) -> int:
    from . import media

    media_root = Path(args.data_dir).expanduser() / "media"
    results = media.add_media([Path(p) for p in args.files], task=args.task, media_root=media_root)
    for url, status in results:
        print(f"{status:8} {url}")
    return 0


def _cmd_verify_media(args: argparse.Namespace) -> int:
    import sqlite3

    from . import media

    data_dir = Path(args.data_dir).expanduser()
    db = data_dir / "field-notes.db"
    media_root = data_dir / "media"
    if not db.is_file():
        print(f"no database at {db}")
        return 1

    refs: set[str] = set()
    con = sqlite3.connect(db)
    try:
        for row in con.execute("SELECT video, body, visual, deep FROM cells"):
            blob = " ".join(str(c) for c in row if c is not None)
            refs |= media.collect_media_refs(blob)
    finally:
        con.close()

    missing = media.missing_media(media_root, refs)
    if missing:
        print(f"{len(missing)} referenced media file(s) MISSING from {media_root}:")
        for m in missing:
            print(f"  {m}")
        return 1
    print(f"all {len(refs)} referenced /media path(s) present in {media_root}")
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir).expanduser()
    print(f"data dir:    {data_dir}")
    print(f"database:    {data_dir / 'field-notes.db'}")
    print(f"media root:  {data_dir / 'media'}")
    print(f"static SPA:  {resolve_static_dir() or '(not bundled — run from source or build _web)'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="field-notes", description="Field Notes local self-host")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="run the local single-process server")
    p_serve.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help=f"default {DEFAULT_DATA_DIR}")
    p_serve.add_argument("--host", default=DEFAULT_HOST, help=f"default {DEFAULT_HOST}")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default {DEFAULT_PORT}")
    p_serve.add_argument("--key", default=None, help="require this API key (else loopback runs keyless)")
    p_serve.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    p_serve.set_defaults(func=_cmd_serve)

    p_addm = sub.add_parser("add-media", help="copy media files into the managed media root")
    p_addm.add_argument("files", nargs="+", help="media files to copy in")
    p_addm.add_argument("--task", required=True, help="subfolder under media/ (the <task> in /media/<task>/...)")
    p_addm.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    p_addm.set_defaults(func=_cmd_add_media)

    p_vfy = sub.add_parser("verify-media", help="report cell media URLs missing from the media root")
    p_vfy.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    p_vfy.set_defaults(func=_cmd_verify_media)

    p_info = sub.add_parser("info", help="print resolved local paths")
    p_info.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    p_info.set_defaults(func=_cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
