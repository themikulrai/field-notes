import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SectionGroup } from "./SectionGroup";
import type { Cell } from "../lib/types";

function mkCell(body: string, overrides: Partial<Cell> = {}): Cell {
  return {
    id: "s1",
    project_id: "p1",
    kind: "markdown",
    position: 0,
    created_at: "",
    updated_at: "",
    locked: false,
    body,
    ...overrides,
  };
}

describe("SectionGroup", () => {
  it("renders heading text and caret", () => {
    render(
      <SectionGroup level={2} heading="Intro" collapsed={false} onToggle={vi.fn()}>
        <div>child</div>
      </SectionGroup>,
    );
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Intro");
    expect(screen.getByLabelText("collapse section")).toBeInTheDocument();
  });

  it("collapse toggle hides children, second click reveals", () => {
    const onToggle = vi.fn();
    const { rerender } = render(
      <SectionGroup level={2} heading="Intro" collapsed={false} onToggle={onToggle}>
        <div data-testid="child">child</div>
      </SectionGroup>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();

    // Click caret -> onToggle called
    fireEvent.click(screen.getByLabelText("collapse section"));
    expect(onToggle).toHaveBeenCalledTimes(1);

    // Re-render in collapsed state to simulate parent flipping the prop.
    rerender(
      <SectionGroup level={2} heading="Intro" collapsed={true} onToggle={onToggle}>
        <div data-testid="child">child</div>
      </SectionGroup>,
    );
    expect(screen.queryByTestId("child")).toBeNull();

    // Click again -> onToggle called once more.
    fireEvent.click(screen.getByLabelText("expand section"));
    expect(onToggle).toHaveBeenCalledTimes(2);

    // Restore: parent expands.
    rerender(
      <SectionGroup level={2} heading="Intro" collapsed={false} onToggle={onToggle}>
        <div data-testid="child">child</div>
      </SectionGroup>,
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });

  it("clicking the heading text also toggles collapse", () => {
    const onToggle = vi.fn();
    render(
      <SectionGroup level={2} heading="Intro" collapsed={false} onToggle={onToggle}>
        <div>child</div>
      </SectionGroup>,
    );
    fireEvent.click(screen.getByText("Intro"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("pencil button enters edit mode, textarea is pre-filled, ⌘+Enter calls onChange with new body", () => {
    const onChange = vi.fn();
    render(
      <SectionGroup
        level={2}
        heading="Intro"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## Intro\n\nsome body text")}
        index={0}
        total={2}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      >
        <div>child</div>
      </SectionGroup>,
    );
    fireEvent.click(screen.getByLabelText("edit section"));
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(ta.value).toBe("## Intro\n\nsome body text");
    fireEvent.change(ta, { target: { value: "## Renamed\n\nbody" } });
    fireEvent.keyDown(ta, { key: "Enter", metaKey: true });
    expect(onChange).toHaveBeenCalledWith("s1", "## Renamed\n\nbody");
  });

  it("Escape in edit mode reverts and does not call onChange", () => {
    const onChange = vi.fn();
    render(
      <SectionGroup
        level={2}
        heading="Intro"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## Intro")}
        index={0}
        total={2}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      >
        <div>child</div>
      </SectionGroup>,
    );
    fireEvent.click(screen.getByLabelText("edit section"));
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "## Changed" } });
    fireEvent.keyDown(ta, { key: "Escape" });
    expect(onChange).not.toHaveBeenCalled();
    // Back in display mode
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Intro");
  });

  it("trash button calls onDelete with cell id", () => {
    const onDelete = vi.fn();
    render(
      <SectionGroup
        level={2}
        heading="Intro"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## Intro")}
        index={1}
        total={3}
        onReorder={vi.fn()}
        onDelete={onDelete}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    fireEvent.click(screen.getByLabelText("delete section"));
    expect(onDelete).toHaveBeenCalledWith("s1");
  });

  it("up disabled when index===0, down disabled when index===total-1; otherwise calls onReorder with direction", () => {
    const onReorder = vi.fn();
    // index=0, total=3 -> up disabled, down enabled
    const { rerender } = render(
      <SectionGroup
        level={2}
        heading="A"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## A")}
        index={0}
        total={3}
        onReorder={onReorder}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    const up0 = screen.getByLabelText("move section up") as HTMLButtonElement;
    const down0 = screen.getByLabelText("move section down") as HTMLButtonElement;
    expect(up0.disabled).toBe(true);
    expect(down0.disabled).toBe(false);
    fireEvent.click(down0);
    expect(onReorder).toHaveBeenCalledWith("s1", "down");

    // index=2, total=3 -> up enabled, down disabled
    rerender(
      <SectionGroup
        level={2}
        heading="A"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## A")}
        index={2}
        total={3}
        onReorder={onReorder}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    const upN = screen.getByLabelText("move section up") as HTMLButtonElement;
    const downN = screen.getByLabelText("move section down") as HTMLButtonElement;
    expect(upN.disabled).toBe(false);
    expect(downN.disabled).toBe(true);
    fireEvent.click(upN);
    expect(onReorder).toHaveBeenLastCalledWith("s1", "up");
  });

  it("clicking action buttons does NOT toggle collapse", () => {
    const onToggle = vi.fn();
    render(
      <SectionGroup
        level={2}
        heading="Intro"
        collapsed={false}
        onToggle={onToggle}
        cell={mkCell("## Intro")}
        index={1}
        total={3}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    fireEvent.click(screen.getByLabelText("move section up"));
    fireEvent.click(screen.getByLabelText("move section down"));
    fireEvent.click(screen.getByLabelText("delete section"));
    // edit button enters edit mode but should also not toggle collapse
    fireEvent.click(screen.getByLabelText("edit section"));
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("starts in edit mode when the heading body is effectively empty (## )", () => {
    render(
      <SectionGroup
        level={2}
        heading=""
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## ")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    // textarea visible immediately, no heading button-mode
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(ta.value).toBe("## ");
  });
});
