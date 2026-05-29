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

  // ---- body-below-heading rendering (fix/section-body-render) ----

  it("renders the body below the heading, including markdown (bold, bullet list, em dash)", () => {
    const { container } = render(
      <SectionGroup
        level={2}
        heading="Vanilla Policy"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell(
          "## Vanilla Policy\n\nThis is **bold** prose — with an em dash.\n\n- first bullet\n- second bullet",
        )}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    const body = container.querySelector(".section-body");
    expect(body).not.toBeNull();
    // prose text present
    expect(body!.textContent).toContain("This is");
    expect(body!.textContent).toContain("with an em dash.");
    // markdown rendered to HTML
    expect(body!.querySelector("strong")?.textContent).toBe("bold");
    const items = body!.querySelectorAll("li");
    expect(items.length).toBe(2);
    expect(items[0].textContent).toBe("first bullet");
    expect(items[1].textContent).toBe("second bullet");
    // heading is NOT duplicated inside the body (only the <h2> from <Head>)
    expect(body!.querySelector("h1, h2, h3, h4")).toBeNull();
    expect(body!.textContent).not.toContain("Vanilla Policy");
  });

  it("does NOT show body text when collapsed", () => {
    const { container } = render(
      <SectionGroup
        level={2}
        heading="Intro"
        collapsed={true}
        onToggle={vi.fn()}
        cell={mkCell("## Intro\n\nhidden body prose here")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div data-testid="child">child</div>
      </SectionGroup>,
    );
    expect(container.querySelector(".section-body")).toBeNull();
    expect(screen.queryByText(/hidden body prose here/)).toBeNull();
  });

  it("renders no non-empty .section-body for a heading-only body", () => {
    const { container } = render(
      <SectionGroup
        level={1}
        heading="Title"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("# Title")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    // no body div at all (guard is `!editing && belowHtml`)
    expect(container.querySelector(".section-body")).toBeNull();
  });

  it("level-4 heading body strips the #### line (no duplicate heading in body)", () => {
    const { container } = render(
      <SectionGroup
        level={3}
        heading="Deep"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("#### Deep\n\ndeep prose")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    const body = container.querySelector(".section-body");
    expect(body).not.toBeNull();
    expect(body!.textContent).toContain("deep prose");
    // the #### line must be stripped positionally, not re-rendered as <h4>
    expect(body!.querySelector("h1, h2, h3, h4")).toBeNull();
    expect(body!.textContent).not.toContain("Deep");
  });

  it("strips correctly with leading blank lines before the heading", () => {
    const { container } = render(
      <SectionGroup
        level={2}
        heading="T"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("\n\n## T\nbody after blanks")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    const body = container.querySelector(".section-body");
    expect(body).not.toBeNull();
    expect(body!.textContent).toContain("body after blanks");
    expect(body!.querySelector("h1, h2, h3, h4")).toBeNull();
  });

  it("handles CRLF line endings", () => {
    const { container } = render(
      <SectionGroup
        level={2}
        heading="T"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## T\r\n\r\nprose crlf\r\n")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div>child</div>
      </SectionGroup>,
    );
    const body = container.querySelector(".section-body");
    expect(body).not.toBeNull();
    expect(body!.textContent).toContain("prose crlf");
    expect(body!.querySelector("h1, h2, h3, h4")).toBeNull();
  });

  it("renders body BEFORE children when a section has both", () => {
    const { container } = render(
      <SectionGroup
        level={2}
        heading="Intro"
        collapsed={false}
        onToggle={vi.fn()}
        cell={mkCell("## Intro\n\nintro body text")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={vi.fn()}
      >
        <div data-testid="child">child</div>
      </SectionGroup>,
    );
    const body = container.querySelector(".section-body");
    const children = container.querySelector(".section-children");
    expect(body).not.toBeNull();
    expect(children).not.toBeNull();
    // .section-body must precede .section-children in DOM order
    expect(
      body!.compareDocumentPosition(children!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("clicking the body enters edit mode (when onChange provided) and does NOT toggle collapse", () => {
    const onToggle = vi.fn();
    const onChange = vi.fn();
    const { container } = render(
      <SectionGroup
        level={2}
        heading="Intro"
        collapsed={false}
        onToggle={onToggle}
        cell={mkCell("## Intro\n\nclickable body")}
        index={0}
        total={1}
        onReorder={vi.fn()}
        onDelete={vi.fn()}
        onChange={onChange}
      >
        <div>child</div>
      </SectionGroup>,
    );
    const body = container.querySelector(".section-body") as HTMLElement;
    expect(body).not.toBeNull();
    fireEvent.click(body);
    // edit mode -> textarea now visible with full body (heading + prose)
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(ta.value).toBe("## Intro\n\nclickable body");
    // body div is gone, collapse not toggled
    expect(container.querySelector(".section-body")).toBeNull();
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("caret-only call site (no cell/onChange) does not render an editable body", () => {
    const { container } = render(
      <SectionGroup level={2} heading="Intro" collapsed={false} onToggle={vi.fn()}>
        <div>child</div>
      </SectionGroup>,
    );
    // No cell/onChange -> no body div at all.
    expect(container.querySelector(".section-body")).toBeNull();
  });
});
