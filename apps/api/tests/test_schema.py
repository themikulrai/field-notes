"""Pydantic schema invariants (independent of the API)."""

from __future__ import annotations

import pytest
from field_notes_schema import (
    CellUpdate,
    ReorderRequest,
    VisualData,
    VisualSandbox,
    VisualSvg,
    VisualVega,
)
from pydantic import ValidationError


def test_reorder_requires_exactly_one() -> None:
    with pytest.raises(ValidationError):
        ReorderRequest()
    with pytest.raises(ValidationError):
        ReorderRequest(direction="up", position=0)
    assert ReorderRequest(direction="up").direction == "up"
    assert ReorderRequest(position=2).position == 2


def test_visual_discriminator() -> None:
    from field_notes_schema import Visual
    from pydantic import TypeAdapter

    ta = TypeAdapter(Visual)
    v = ta.validate_python({"kind": "data", "chart": "line", "series": []})
    assert isinstance(v, VisualData)
    v = ta.validate_python({"kind": "vega", "spec": {}})
    assert isinstance(v, VisualVega)
    v = ta.validate_python({"kind": "svg", "source": "<svg/>"})
    assert isinstance(v, VisualSvg)
    v = ta.validate_python({"kind": "sandbox", "html": "", "js": "", "css": ""})
    assert isinstance(v, VisualSandbox)


def test_cell_update_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        CellUpdate(verdict={"state": "accept"})  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        CellUpdate(locked=True)  # type: ignore[arg-type]
    # Valid update OK.
    upd = CellUpdate(title="x")
    assert upd.title == "x"
