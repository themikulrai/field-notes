"""Schema package is importable & discriminator works on its own."""

from __future__ import annotations

from field_notes_schema import (
    Visual,
    VisualData,
    VisualSandbox,
    VisualSvg,
    VisualVega,
)
from pydantic import TypeAdapter


def test_visual_discriminator() -> None:
    ta = TypeAdapter(Visual)
    assert isinstance(ta.validate_python({"kind": "data", "chart": "bar", "series": []}), VisualData)
    assert isinstance(ta.validate_python({"kind": "vega", "spec": {"$schema": "vl"}}), VisualVega)
    assert isinstance(ta.validate_python({"kind": "svg", "source": "<svg/>"}), VisualSvg)
    assert isinstance(ta.validate_python({"kind": "sandbox"}), VisualSandbox)
