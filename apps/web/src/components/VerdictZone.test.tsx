import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VerdictZone } from "./VerdictZone";
import type { Cell as CellData } from "../lib/types";

function mkCell(overrides: Partial<CellData> = {}): CellData {
  return {
    id: "c1",
    project_id: "p1",
    kind: "agent",
    position: 0,
    created_at: "2026-05-15T12:00:00Z",
    updated_at: "2026-05-15T12:00:00Z",
    title: "run 4",
    status: "open",
    locked: false,
    ...overrides,
  };
}

describe("VerdictZone", () => {
  it("no verdict: clicking verify calls onVerdict('accept', '')", () => {
    const onVerdict = vi.fn();
    render(<VerdictZone cell={mkCell()} onVerdict={onVerdict} onUnlock={vi.fn()} />);
    fireEvent.click(screen.getByText("verify"));
    expect(onVerdict).toHaveBeenCalledWith("accept", "");
  });

  it("consistent verified cell: button reads 'verified' and one click toggles OFF (clears)", () => {
    const onVerdict = vi.fn();
    const cell = mkCell({
      status: "verified",
      verdict: { state: "accept", note: "looks right", by: "you", at: "2026-05-15T12:00:00Z" },
    });
    render(<VerdictZone cell={cell} onVerdict={onVerdict} onUnlock={vi.fn()} />);
    // active state reflects the cell status → label is "verified"
    expect(screen.getByText("verified")).toBeInTheDocument();
    fireEvent.click(screen.getByText("verified"));
    // toggling off clears the verdict
    expect(onVerdict).toHaveBeenCalledWith(null, "looks right");
  });

  it("stale verdict (status=open but verdict=accept): does NOT show 'verified' active, and one click RE-CONFIRMS", () => {
    // Regression: an agent edit re-opens a verified cell (status→open) but leaves
    // the accept verdict, so the cell showed blue+verified at once and the human
    // had to click verify twice. The button must NOT read as the active verified
    // state, and a single click must re-apply (not clear).
    const onVerdict = vi.fn();
    const cell = mkCell({
      status: "open",
      verdict: { state: "accept", note: "looked right", by: "you", at: "2026-05-15T12:00:00Z" },
    });
    render(<VerdictZone cell={cell} onVerdict={onVerdict} onUnlock={vi.fn()} />);
    // Not in the active "verified" presentation.
    expect(screen.queryByText("verified")).toBeNull();
    // A stale-re-confirm hint is shown.
    expect(screen.getByText(/changed since/i)).toBeInTheDocument();
    // Single click re-applies the accept verdict (preserving the note).
    fireEvent.click(screen.getByText(/^verify/));
    expect(onVerdict).toHaveBeenCalledWith("accept", "looked right");
  });
});
