// Verify that a `resync` SSE event triggers loadProjects + loadCells.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import type { EventEnvelope } from "./types";

type Listener = (env: EventEnvelope) => void;

let capturedListener: Listener | null = null;

vi.mock("./events", () => ({
  openEventStream: (_projectId: string, listener: Listener) => {
    capturedListener = listener;
    return { close: () => {} };
  },
}));

describe("useLiveEvents resync handling", () => {
  beforeEach(() => {
    capturedListener = null;
    localStorage.setItem("field-notes-key", "k");
    vi.resetModules();
  });

  it("calls loadProjects and loadCells when a resync event arrives", async () => {
    const { useStore } = await import("./store");
    const { useLiveEvents } = await import("./live");

    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: { p1: [] },
    });

    const loadProjects = vi.fn().mockResolvedValue(undefined);
    const loadCells = vi.fn().mockResolvedValue(undefined);
    useStore.setState({ loadProjects, loadCells } as Partial<ReturnType<typeof useStore.getState>>);

    renderHook(() => useLiveEvents());

    expect(capturedListener).not.toBeNull();
    capturedListener!({ kind: "resync", at: new Date().toISOString() } as unknown as EventEnvelope);

    // applyEvent + refetch are async; allow microtasks to drain.
    await Promise.resolve();
    await Promise.resolve();

    expect(loadProjects).toHaveBeenCalledTimes(1);
    expect(loadCells).toHaveBeenCalledWith("p1");
  });

  it("does NOT refetch for normal events", async () => {
    const { useStore } = await import("./store");
    const { useLiveEvents } = await import("./live");

    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: { p1: [] },
    });
    const loadProjects = vi.fn().mockResolvedValue(undefined);
    const loadCells = vi.fn().mockResolvedValue(undefined);
    const applyEvent = vi.fn().mockResolvedValue(undefined);
    useStore.setState({ loadProjects, loadCells, applyEvent } as Partial<ReturnType<typeof useStore.getState>>);

    renderHook(() => useLiveEvents());
    expect(capturedListener).not.toBeNull();
    capturedListener!({
      id: "e1",
      kind: "cell.updated",
      project_id: "p1",
      at: new Date().toISOString(),
    } as unknown as EventEnvelope);
    await Promise.resolve();
    await Promise.resolve();

    expect(loadProjects).not.toHaveBeenCalled();
    expect(loadCells).not.toHaveBeenCalled();
    expect(applyEvent).toHaveBeenCalledTimes(1);
  });
});
