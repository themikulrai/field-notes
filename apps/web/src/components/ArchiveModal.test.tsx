import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ArchiveModal } from "./ArchiveModal";

const proj = (id: string, name: string) => ({ id, name }) as any;

describe("ArchiveModal", () => {
  it("lists archived projects and fires unarchive/delete", () => {
    const onUnarchive = vi.fn();
    const onDelete = vi.fn();
    render(
      <ArchiveModal
        projects={[proj("p1", "alpha")]}
        onUnarchive={onUnarchive}
        onDelete={onDelete}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText("alpha")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /unarchive alpha/i }));
    expect(onUnarchive).toHaveBeenCalledWith("p1");

    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(screen.getByRole("button", { name: /delete alpha/i }));
    expect(onDelete).toHaveBeenCalledWith("p1");
  });

  it("shows an empty state when nothing is archived", () => {
    render(
      <ArchiveModal projects={[]} onUnarchive={() => {}} onDelete={() => {}} onClose={() => {}} />,
    );
    expect(screen.getByText(/no archived projects/i)).toBeInTheDocument();
  });

  it("closes on Escape and backdrop click", () => {
    const onClose = vi.fn();
    render(
      <ArchiveModal projects={[]} onUnarchive={() => {}} onDelete={() => {}} onClose={onClose} />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("archive-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
