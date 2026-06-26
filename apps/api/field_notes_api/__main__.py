"""CLI entrypoint for `field-notes-api`."""

from __future__ import annotations


def main() -> None:
    """Run the FastAPI app under uvicorn.

    Host/port come from env: FIELD_NOTES_HOST (default 0.0.0.0 for container
    deploys) and $PORT (Heroku) / FIELD_NOTES_PORT (default 8000). The local
    single-process path uses `field-notes serve` instead, which binds loopback.
    """
    import os

    import uvicorn

    host = os.getenv("FIELD_NOTES_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("FIELD_NOTES_PORT") or "8000")

    uvicorn.run(
        "field_notes_api.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
