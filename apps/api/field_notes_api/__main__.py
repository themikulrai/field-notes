"""CLI entrypoint for `field-notes-api`."""

from __future__ import annotations


def main() -> None:
    """Run the FastAPI app under uvicorn."""
    # TODO: Chunk 2 — wire env-driven host/port/log-level via pydantic-settings.
    import uvicorn

    uvicorn.run(
        "field_notes_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
