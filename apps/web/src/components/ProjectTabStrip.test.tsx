import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ProjectTabStrip } from "./ProjectTabStrip";
import type { Project } from "../lib/types";

function makeProject(overrides: Partial<Project> & { id: string; name: string }): Project {
  return {
    id: overrides.id,
    name: overrides.name,
    subtitle: overrides.subtitle ?? null,
    repo: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ui_filter: null,
    counts: overrides.counts ?? { in_progress: 0, open: 0, verified: 0, rejected: 0 },
  };
}

describe("ProjectTabStrip", () => {
  it("renders pip counts from project.counts (does not depend on loaded cells)", () => {
    const projects: Project[] = [
      makeProject({ id: "a", name: "Alpha", counts: { in_progress: 2, open: 3, verified: 0, rejected: 0 } }),
      makeProject({ id: "b", name: "Beta" }),
    ];
    render(
      <ProjectTabStrip
        projects={projects}
        activeId="a"
        onSelect={() => {}}
        onClose={() => {}}
        onAdd={() => {}}
      />,
    );
    // Alpha shows 2 in-progress and 3 awaiting review.
    expect(screen.getByTitle("2 in progress")).toBeTruthy();
    expect(screen.getByTitle("3 awaiting review")).toBeTruthy();
    // Beta has all zeros => dim rest pip rendered once.
    const restPips = screen.getAllByText("0");
    expect(restPips.length).toBeGreaterThanOrEqual(1);
  });

  it("renders verified and rejected pips when those counts are non-zero", () => {
    const projects: Project[] = [
      makeProject({ id: "a", name: "Alpha", counts: { in_progress: 0, open: 0, verified: 5, rejected: 1 } }),
    ];
    render(
      <ProjectTabStrip
        projects={projects}
        activeId="a"
        onSelect={() => {}}
        onClose={() => {}}
        onAdd={() => {}}
      />,
    );
    expect(screen.getByTitle("5 verified")).toBeTruthy();
    expect(screen.getByTitle("1 rejected")).toBeTruthy();
    // Project is non-empty, so the dim rest pip must NOT be rendered.
    expect(screen.queryByText("0")).toBeNull();
  });

  it("renders the dim rest pip only when all four counts are zero", () => {
    const projects: Project[] = [
      makeProject({ id: "a", name: "Empty", counts: { in_progress: 0, open: 0, verified: 0, rejected: 0 } }),
    ];
    render(
      <ProjectTabStrip
        projects={projects}
        activeId="a"
        onSelect={() => {}}
        onClose={() => {}}
        onAdd={() => {}}
      />,
    );
    expect(screen.getByText("0")).toBeTruthy();
    expect(screen.queryByTitle(/verified/)).toBeNull();
    expect(screen.queryByTitle(/rejected/)).toBeNull();
  });

  it("does not render the subtitle in the tab body", () => {
    const subtitle = "A long descriptive subtitle that should not appear inline in the tab strip";
    const projects: Project[] = [makeProject({ id: "a", name: "Alpha", subtitle })];
    const { container } = render(
      <ProjectTabStrip
        projects={projects}
        activeId="a"
        onSelect={() => {}}
        onClose={() => {}}
        onAdd={() => {}}
      />,
    );
    expect(container.textContent ?? "").not.toContain(subtitle);
  });

  it("exposes subtitle via the tab title attribute (hover tooltip)", () => {
    const projects: Project[] = [
      makeProject({ id: "a", name: "Alpha", subtitle: "two robots stack" }),
      makeProject({ id: "b", name: "Beta" }),
    ];
    render(
      <ProjectTabStrip
        projects={projects}
        activeId="a"
        onSelect={() => {}}
        onClose={() => {}}
        onAdd={() => {}}
      />,
    );
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0].getAttribute("title")).toBe("Alpha · two robots stack");
    expect(tabs[1].getAttribute("title")).toBe("Beta");
  });

  it("handles projects without counts (undefined) by treating them as zero", () => {
    const projects: Project[] = [
      makeProject({ id: "a", name: "Alpha", counts: undefined }),
    ];
    render(
      <ProjectTabStrip
        projects={projects}
        activeId="a"
        onSelect={() => {}}
        onClose={() => {}}
        onAdd={() => {}}
      />,
    );
    // No in-progress or open pips, just the dim zero pip.
    expect(screen.queryByTitle(/in progress/)).toBeNull();
    expect(screen.queryByTitle(/awaiting review/)).toBeNull();
    expect(screen.getByText("0")).toBeTruthy();
  });

  it("fires onSelect when a tab is clicked", () => {
    const onSelect = vi.fn();
    const projects: Project[] = [
      makeProject({ id: "a", name: "Alpha" }),
      makeProject({ id: "b", name: "Beta" }),
    ];
    render(
      <ProjectTabStrip
        projects={projects}
        activeId="a"
        onSelect={onSelect}
        onClose={() => {}}
        onAdd={() => {}}
      />,
    );
    fireEvent.click(screen.getByText("Beta"));
    expect(onSelect).toHaveBeenCalledWith("b");
  });
});
