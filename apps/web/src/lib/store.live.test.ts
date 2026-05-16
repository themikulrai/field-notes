// Live SSE event handling: ui.filter_changed must update the Zustand `filter`
// state without triggering an API write back to the server (filter is event-
// driven only — the MCP set_filter / API endpoint emits the event, the store
// just reflects it).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const ORIG_FETCH = globalThis.fetch;

describe("ui.filter_changed SSE event handling", () => {
  beforeEach(() => {
    localStorage.setItem("field-notes-key", "k");
    vi.resetModules();
  });
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH;
    localStorage.clear();
  });

  it("applyEvent('ui.filter_changed') updates filter and makes NO API call", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: { p1: [] },
      filter: "all",
    });

    const fetchMock = vi.fn();
    globalThis.fetch = fetchMock as typeof fetch;

    await useStore.getState().applyEvent({
      id: "evt-1",
      kind: "ui.filter_changed",
      project_id: "p1",
      payload: { filter: "verified" },
    });

    expect(useStore.getState().filter).toBe("verified");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("applyEvent ignores ui.filter_changed for a non-active project", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [
        { id: "p1", name: "P1", created_at: "", updated_at: "" },
        { id: "p2", name: "P2", created_at: "", updated_at: "" },
      ],
      activeProjectId: "p1",
      cellsByProject: { p1: [], p2: [] },
      filter: "all",
    });

    await useStore.getState().applyEvent({
      id: "evt-2",
      kind: "ui.filter_changed",
      project_id: "p2",
      payload: { filter: "rejected" },
    });

    expect(useStore.getState().filter).toBe("all");
  });

  it("applyEvent ignores garbage filter values", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: { p1: [] },
      filter: "open",
    });

    await useStore.getState().applyEvent({
      id: "evt-3",
      kind: "ui.filter_changed",
      project_id: "p1",
      payload: { filter: "this-is-not-a-filter" },
    });

    expect(useStore.getState().filter).toBe("open");
  });

  it("setActiveProject seeds filter from project's persisted ui_filter", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [
        { id: "p1", name: "P1", created_at: "", updated_at: "", ui_filter: "rejected" },
      ],
      activeProjectId: null,
      cellsByProject: {},
      filter: "all",
    });

    useStore.getState().setActiveProject("p1");
    expect(useStore.getState().filter).toBe("rejected");
  });

  it("loadCells initializes filter pill from project ui_filter when project is active", async () => {
    const { useStore } = await import("./store");
    // Stub fetch for the listCells call.
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200, headers: { "content-type": "application/json" } }),
    ) as typeof fetch;
    useStore.setState({
      projects: [{ id: "p1", name: "P1", created_at: "", updated_at: "", ui_filter: "verified" }],
      activeProjectId: "p1",
      cellsByProject: {},
      filter: "all",
    });

    await useStore.getState().loadCells("p1");
    expect(useStore.getState().filter).toBe("verified");
  });
});
