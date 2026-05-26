// Verify that a `resync` SSE event triggers loadProjects + loadCells.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";

type ESHandler = ((ev: MessageEvent<string>) => void) | null;

class MockEventSource {
  static last: MockEventSource | null = null;
  onmessage: ESHandler = null;
  onopen: (() => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    MockEventSource.last = this;
  }
  close() {}
  emit(data: string) {
    this.onmessage?.({ data } as MessageEvent<string>);
  }
}

const ORIG_ES = (globalThis as { EventSource?: unknown }).EventSource;

describe("useLiveEvents resync handling", () => {
  beforeEach(() => {
    localStorage.setItem("field-notes-key", "k");
    (globalThis as unknown as { EventSource: unknown }).EventSource = MockEventSource;
    vi.resetModules();
  });
  afterEach(() => {
    (globalThis as unknown as { EventSource: unknown }).EventSource = ORIG_ES;
    localStorage.clear();
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

    expect(MockEventSource.last).not.toBeNull();
    MockEventSource.last!.emit(JSON.stringify({ kind: "resync", at: new Date().toISOString() }));

    // applyEvent is async; allow microtasks to drain.
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
    MockEventSource.last!.emit(
      JSON.stringify({ id: "e1", kind: "cell.updated", project_id: "p1", at: new Date().toISOString() }),
    );
    await Promise.resolve();
    await Promise.resolve();

    expect(loadProjects).not.toHaveBeenCalled();
    expect(loadCells).not.toHaveBeenCalled();
    expect(applyEvent).toHaveBeenCalledTimes(1);
  });
});
