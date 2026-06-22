import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Cell } from "./Cell";
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
    agent_id: "agent-orca-7",
    status: "open",
    conclusion: "Run 4 looks good.",
    metrics: [{ k: "success", v: "0.74" }],
    locked: false,
    ...overrides,
  };
}

describe("Cell", () => {
  it("renders status, conclusion, and metrics", () => {
    render(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("run 4")).toBeInTheDocument();
    expect(screen.getByText("Run 4 looks good.")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("0.74")).toBeInTheDocument();
    expect(screen.getByLabelText("status: open")).toBeInTheDocument();
  });

  it("clicking verify calls onVerdict('accept', '')", () => {
    const spy = vi.fn();
    render(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={spy}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("verify"));
    expect(spy).toHaveBeenCalledWith("c1", "accept", "");
  });

  it("when locked, no verify/reject; unlock button is present", () => {
    const cell = mkCell({
      locked: true,
      verdict: { state: "accept", note: "ok", by: "you", at: "2026-05-15T12:00:00Z" },
      status: "verified",
    });
    render(
      <Cell
        cell={cell}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.queryByText("verify")).toBeNull();
    expect(screen.queryByText("reject")).toBeNull();
    expect(screen.getByText("unlock")).toBeInTheDocument();
    expect(screen.getAllByText("LOCKED").length).toBeGreaterThan(0);
  });

  it("with no verdict + draft, label shows 'verify with comment'", () => {
    render(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    const ta = screen.getByPlaceholderText(/write what you think/);
    fireEvent.change(ta, { target: { value: "hmm" } });
    expect(screen.getByText("verify with comment")).toBeInTheDocument();
    expect(screen.getByText("reject with comment")).toBeInTheDocument();
  });

  it("renders an unknown/deprecated status (e.g. 'ready') without throwing", () => {
    // Regression: STATUSES had no 'ready' key, so STATUSES['ready'].rail threw
    // and white-screened the whole app. statusMeta() now falls back to 'open'.
    const cell = mkCell({ status: "ready" as unknown as CellData["status"] });
    expect(() =>
      render(
        <Cell
          cell={cell}
          index={0}
          total={1}
          onReorder={vi.fn()}
          onVerdict={vi.fn()}
          onUnlock={vi.fn()}
          onDelete={vi.fn()}
          onChange={vi.fn()}
        />,
      ),
    ).not.toThrow();
    // degrades to the "open" (needs-review) presentation
    expect(screen.getByText("run 4")).toBeInTheDocument();
    expect(screen.getByLabelText("status: open")).toBeInTheDocument();
  });

  it("double-clicking the title enters edit and does NOT toggle collapse", () => {
    const toggle = vi.fn();
    render(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        onToggleCollapse={toggle}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    fireEvent.doubleClick(screen.getByText("run 4"));
    expect(toggle).not.toHaveBeenCalled();
    expect(screen.getByLabelText("edit title")).toBeInTheDocument();
  });

  it("saving the title calls onChange with { title }", () => {
    const onChange = vi.fn();
    render(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      />,
    );
    fireEvent.doubleClick(screen.getByText("run 4"));
    const input = screen.getByLabelText("edit title");
    fireEvent.change(input, { target: { value: "run 5" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("c1", { title: "run 5" });
  });

  it("saving the conclusion calls onChange with { conclusion }", () => {
    const onChange = vi.fn();
    render(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      />,
    );
    fireEvent.doubleClick(screen.getByText("Run 4 looks good."));
    const ta = screen.getByLabelText("edit conclusion");
    fireEvent.change(ta, { target: { value: "Run 4 is great." } });
    fireEvent.keyDown(ta, { key: "Enter", metaKey: true });
    expect(onChange).toHaveBeenCalledWith("c1", { conclusion: "Run 4 is great." });
  });

  it("a locked cell does not enter edit mode on double-click", () => {
    render(
      <Cell
        cell={mkCell({ locked: true })}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    fireEvent.doubleClick(screen.getByText("run 4"));
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("empty-conclusion cell shows an editable 'add conclusion' target", () => {
    const onChange = vi.fn();
    render(
      <Cell
        cell={mkCell({ conclusion: "" })}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      />,
    );
    const target = screen.getByText(/add conclusion/i);
    fireEvent.doubleClick(target);
    const ta = screen.getByLabelText("edit conclusion");
    fireEvent.change(ta, { target: { value: "now concluded" } });
    fireEvent.keyDown(ta, { key: "Enter", metaKey: true });
    expect(onChange).toHaveBeenCalledWith("c1", { conclusion: "now concluded" });
  });

  it("when collapsed, hides conclusion + metrics; clicking header toggles", () => {
    const toggle = vi.fn();
    const { rerender } = render(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        collapsed
        onToggleCollapse={toggle}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("run 4")).toBeInTheDocument();
    expect(screen.queryByText("Run 4 looks good.")).not.toBeInTheDocument();
    expect(screen.queryByText("0.74")).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("expand cell"));
    expect(toggle).toHaveBeenCalledTimes(1);

    rerender(
      <Cell
        cell={mkCell()}
        index={0}
        total={1}
        collapsed={false}
        onToggleCollapse={toggle}
        onReorder={vi.fn()}
        onVerdict={vi.fn()}
        onUnlock={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText("Run 4 looks good.")).toBeInTheDocument();
  });
});
