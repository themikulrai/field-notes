import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InlineEdit } from "./InlineEdit";

function setup(props: Partial<React.ComponentProps<typeof InlineEdit>> = {}) {
  const onSave = props.onSave ?? vi.fn();
  render(
    <InlineEdit
      value={props.value ?? "hello"}
      multiline={props.multiline ?? false}
      disabled={props.disabled ?? false}
      renderView={props.renderView ?? (() => <span>{props.value ?? "hello"}</span>)}
      onSave={onSave}
      ariaLabel={props.ariaLabel}
      placeholder={props.placeholder}
    />,
  );
  return { onSave };
}

describe("InlineEdit", () => {
  it("double-click enters edit mode (input appears)", () => {
    setup({ value: "hello" });
    expect(screen.queryByRole("textbox")).toBeNull();
    fireEvent.doubleClick(screen.getByText("hello"));
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect((screen.getByRole("textbox") as HTMLInputElement).value).toBe("hello");
  });

  it("single-line: Enter saves changed value", () => {
    const { onSave } = setup({ value: "hello", multiline: false });
    fireEvent.doubleClick(screen.getByText("hello"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "world" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSave).toHaveBeenCalledWith("world");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("single-line: blur saves changed value", () => {
    const { onSave } = setup({ value: "hello", multiline: false });
    fireEvent.doubleClick(screen.getByText("hello"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "world" } });
    fireEvent.blur(input);
    expect(onSave).toHaveBeenCalledWith("world");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("multiline: Cmd/Ctrl+Enter saves; plain Enter does NOT save", () => {
    const { onSave } = setup({ value: "hello", multiline: true });
    fireEvent.doubleClick(screen.getByText("hello"));
    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "world" } });
    // plain Enter should not save (inserts newline in real textarea)
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    // Cmd+Enter saves
    fireEvent.keyDown(ta, { key: "Enter", metaKey: true });
    expect(onSave).toHaveBeenCalledWith("world");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("Esc cancels: draft discarded, onSave NOT called", () => {
    const { onSave } = setup({ value: "hello" });
    fireEvent.doubleClick(screen.getByText("hello"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "world" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("unchanged value: onSave NOT called, still exits edit mode", () => {
    const { onSave } = setup({ value: "hello" });
    fireEvent.doubleClick(screen.getByText("hello"));
    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("disabled: double-click does nothing", () => {
    setup({ value: "hello", disabled: true });
    fireEvent.doubleClick(screen.getByText("hello"));
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});
