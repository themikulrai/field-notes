import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerdictZone } from "./VerdictZone";
import type { Cell, Verdict } from "../lib/types";

function mk(updated_at: string, verdict: Verdict | null, locked = false): Cell {
  return {
    id: "c1",
    project_id: "p1",
    kind: "agent",
    position: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at,
    locked,
    verdict,
  };
}

const V = (at: string): Verdict => ({
  state: "accept",
  note: "",
  by: "human",
  at,
});

describe("VerdictZone STALE indicator", () => {
  it("renders STALE when updated_at > v.at", () => {
    render(
      <VerdictZone
        cell={mk("2026-05-25T12:00:00Z", V("2026-05-25T10:00:00Z"))}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
      />,
    );
    expect(screen.getByText("STALE")).toBeInTheDocument();
  });

  it("no STALE when updated_at <= v.at", () => {
    render(
      <VerdictZone
        cell={mk("2026-05-25T10:00:00Z", V("2026-05-25T12:00:00Z"))}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
      />,
    );
    expect(screen.queryByText("STALE")).not.toBeInTheDocument();
  });

  it("no STALE when updated_at == v.at", () => {
    const t = "2026-05-25T10:00:00Z";
    render(
      <VerdictZone
        cell={mk(t, V(t))}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
      />,
    );
    expect(screen.queryByText("STALE")).not.toBeInTheDocument();
  });

  it("no STALE when verdict is null", () => {
    render(
      <VerdictZone
        cell={mk("2026-05-25T12:00:00Z", null)}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
      />,
    );
    expect(screen.queryByText("STALE")).not.toBeInTheDocument();
  });

  it("STALE has the title attribute", () => {
    render(
      <VerdictZone
        cell={mk("2026-05-25T12:00:00Z", V("2026-05-25T10:00:00Z"))}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
      />,
    );
    const chip = screen.getByText("STALE");
    expect(chip.getAttribute("title")).toBe(
      "cell edited after verdict — please re-review",
    );
  });

  it("renders STALE in locked-cell branch too", () => {
    render(
      <VerdictZone
        cell={mk("2026-05-25T12:00:00Z", V("2026-05-25T10:00:00Z"), true)}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
      />,
    );
    expect(screen.getByText("STALE")).toBeInTheDocument();
    expect(screen.getByText("LOCKED")).toBeInTheDocument();
  });
});
