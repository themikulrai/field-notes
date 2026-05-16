"""Field Notes MCP server package.

The agent's view of Field Notes. Exposes read/write tools for projects + cells
plus a `get_feedback` shortcut so the agent can quickly see which conclusions
the human accepted, rejected, or locked. Verdict / lock writes are
deliberately NOT exposed — those are the human's authority.

Two transports:
    field_notes_mcp.__main__       — stdio (Claude Code, Claude Desktop)
    field_notes_mcp.http_server    — HTTP/SSE (remote)

Shared tool definitions live in `tools.py` (transport-agnostic).
"""

from .client import FieldNotesAPIError, FieldNotesClient, LockedCellError
from .tools import HUMAN_ONLY_TOOLS, TOOL_NAMES, register_tools

__version__ = "0.1.0"

__all__ = [
    "HUMAN_ONLY_TOOLS",
    "TOOL_NAMES",
    "FieldNotesAPIError",
    "FieldNotesClient",
    "LockedCellError",
    "register_tools",
]
