import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MarkdownCell } from "./MarkdownCell";
import type { Cell } from "../lib/types";

function mk(body: string): Cell {
  return {
    id: "m1",
    project_id: "p1",
    kind: "markdown",
    position: 0,
    created_at: "",
    updated_at: "",
    locked: false,
    body,
  };
}

describe("MarkdownCell", () => {
  it("renders # H1 as <h1>", () => {
    render(
      <MarkdownCell
        cell={mk("# Hello")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      />,
    );
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBe("Hello");
  });

  it("click to edit, ⌘+Enter saves and exits edit mode", () => {
    const onChange = vi.fn();
    render(
      <MarkdownCell
        cell={mk("# Hello")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText("Hello"));
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "# Updated" } });
    fireEvent.keyDown(ta, { key: "Enter", metaKey: true });
    expect(onChange).toHaveBeenCalledWith("m1", "# Updated");
  });

  it("esc cancels and preserves original body", () => {
    const onChange = vi.fn();
    render(
      <MarkdownCell
        cell={mk("# Original")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText("Original"));
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "# changed" } });
    fireEvent.keyDown(ta, { key: "Escape" });
    // After esc, rendered view returns; onChange was NOT called yet.
    // (textarea onBlur could fire after Escape and call commit; jsdom doesn't
    // trigger blur from key, so we're safe.)
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Original")).toBeInTheDocument();
  });
});
