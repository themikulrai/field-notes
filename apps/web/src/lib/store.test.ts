import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const ORIG_FETCH = globalThis.fetch;

function mkRes(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("store optimistic updates", () => {
  beforeEach(() => {
    localStorage.setItem("field-notes-key", "k");
    vi.resetModules();
  });
  afterEach(() => {
    globalThis.fetch = ORIG_FETCH;
    localStorage.clear();
  });

  it("setVerdict updates local state immediately, then reconciles with server response", async () => {
    const { useStore } = await import("./store");
    // Pre-populate one cell
    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: {
        p1: [
          {
            id: "c1",
            project_id: "p1",
            kind: "agent",
            position: 0,
            created_at: "",
            updated_at: "",
            locked: false,
            status: "open",
            title: "x",
          },
        ],
      },
    });

    let resolve!: (v: Response) => void;
    const pending = new Promise<Response>((r) => {
      resolve = r;
    });
    globalThis.fetch = vi.fn().mockReturnValue(pending) as typeof fetch;

    const p = useStore.getState().setVerdict("c1", "accept", "good");
    // After dispatch but before server resolves, status should already be 'verified'.
    expect(useStore.getState().cellsByProject.p1[0].status).toBe("verified");
    expect(useStore.getState().cellsByProject.p1[0].verdict?.state).toBe("accept");

    // Resolve server with a slightly different note to confirm reconciliation.
    resolve(
      mkRes({
        id: "c1",
        project_id: "p1",
        kind: "agent",
        position: 0,
        created_at: "",
        updated_at: "",
        locked: false,
        status: "verified",
        verdict: { state: "accept", note: "server-note", by: "you", at: "2026-05-15" },
      }),
    );
    await p;
    expect(useStore.getState().cellsByProject.p1[0].verdict?.note).toBe("server-note");
  });

  it("reorderCell up swaps cells locally before server confirms", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: {
        p1: [
          { id: "a", project_id: "p1", kind: "agent", position: 0, created_at: "", updated_at: "", locked: false, status: "open" },
          { id: "b", project_id: "p1", kind: "agent", position: 1, created_at: "", updated_at: "", locked: false, status: "open" },
        ],
      },
    });
    let resolve!: (v: Response) => void;
    const pending = new Promise<Response>((r) => {
      resolve = r;
    });
    globalThis.fetch = vi.fn().mockReturnValue(pending) as typeof fetch;

    const p = useStore.getState().reorderCell("b", "up");
    expect(useStore.getState().cellsByProject.p1.map((c) => c.id)).toEqual(["b", "a"]);
    resolve(mkRes({}));
    // After server returns, reorderCell calls loadCells; that's another fetch
    // — but we don't await it strictly here; resolve again.
    const fm = globalThis.fetch as ReturnType<typeof vi.fn>;
    fm.mockResolvedValue(
      mkRes([
        { id: "b", project_id: "p1", kind: "agent", position: 0, created_at: "", updated_at: "", locked: false, status: "open" },
        { id: "a", project_id: "p1", kind: "agent", position: 1, created_at: "", updated_at: "", locked: false, status: "open" },
      ]),
    );
    await p;
    expect(useStore.getState().cellsByProject.p1.map((c) => c.id)).toEqual(["b", "a"]);
  });

  it("toggleSection persists in localStorage and round-trips", async () => {
    const { useStore } = await import("./store");
    useStore.getState().toggleSection("p1", "h:0");
    expect(useStore.getState().isSectionCollapsed("p1", "h:0")).toBe(true);
    const raw = localStorage.getItem("field-notes-collapsed");
    expect(raw && JSON.parse(raw).p1["h:0"]).toBe(true);
  });

  it("deleteProject resets activeProjectId to a remaining project when the active one is deleted", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [
        { id: "p1", name: "P1", created_at: "", updated_at: "" },
        { id: "p2", name: "P2", created_at: "", updated_at: "" },
      ],
      activeProjectId: "p1",
      cellsByProject: {},
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 })) as typeof fetch;
    await useStore.getState().deleteProject("p1");
    expect(useStore.getState().projects.map((p) => p.id)).toEqual(["p2"]);
    expect(useStore.getState().activeProjectId).toBe("p2");
  });

  it("deleteProject sets activeProjectId to null when last project is deleted", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [{ id: "only", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "only",
      cellsByProject: {},
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 })) as typeof fetch;
    await useStore.getState().deleteProject("only");
    expect(useStore.getState().projects).toEqual([]);
    expect(useStore.getState().activeProjectId).toBeNull();
  });

  it("createCell splices the new cell after the anchor (after_cell_id = A.id → [A, new, B, C])", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: {
        p1: [
          { id: "A", project_id: "p1", kind: "markdown", position: 0, created_at: "", updated_at: "", locked: false, body: "a" },
          { id: "B", project_id: "p1", kind: "markdown", position: 1, created_at: "", updated_at: "", locked: false, body: "b" },
          { id: "C", project_id: "p1", kind: "markdown", position: 2, created_at: "", updated_at: "", locked: false, body: "c" },
        ],
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(
      mkRes({
        id: "NEW",
        project_id: "p1",
        kind: "markdown",
        position: 1,
        created_at: "",
        updated_at: "",
        locked: false,
        body: "",
      }),
    ) as typeof fetch;

    await useStore.getState().createCell("p1", { kind: "markdown", after_cell_id: "A", body: "" });
    expect(useStore.getState().cellsByProject.p1.map((c) => c.id)).toEqual(["A", "NEW", "B", "C"]);
    // No follow-up loadCells: exactly one fetch (the POST).
    expect((globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(1);
  });

  it("createCell with null anchor inserts at the top (→ [new, A, B, C])", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: {
        p1: [
          { id: "A", project_id: "p1", kind: "markdown", position: 0, created_at: "", updated_at: "", locked: false, body: "a" },
          { id: "B", project_id: "p1", kind: "markdown", position: 1, created_at: "", updated_at: "", locked: false, body: "b" },
          { id: "C", project_id: "p1", kind: "markdown", position: 2, created_at: "", updated_at: "", locked: false, body: "c" },
        ],
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(
      mkRes({
        id: "NEW",
        project_id: "p1",
        kind: "markdown",
        position: 0,
        created_at: "",
        updated_at: "",
        locked: false,
        body: "",
      }),
    ) as typeof fetch;

    await useStore.getState().createCell("p1", { kind: "markdown", after_cell_id: null, body: "" });
    expect(useStore.getState().cellsByProject.p1.map((c) => c.id)).toEqual(["NEW", "A", "B", "C"]);
  });

  it("createCell with a missing anchor defensively appends to the end", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [{ id: "p1", name: "P", created_at: "", updated_at: "" }],
      activeProjectId: "p1",
      cellsByProject: {
        p1: [
          { id: "A", project_id: "p1", kind: "markdown", position: 0, created_at: "", updated_at: "", locked: false, body: "a" },
          { id: "B", project_id: "p1", kind: "markdown", position: 1, created_at: "", updated_at: "", locked: false, body: "b" },
          { id: "C", project_id: "p1", kind: "markdown", position: 2, created_at: "", updated_at: "", locked: false, body: "c" },
        ],
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue(
      mkRes({
        id: "NEW",
        project_id: "p1",
        kind: "markdown",
        position: 3,
        created_at: "",
        updated_at: "",
        locked: false,
        body: "",
      }),
    ) as typeof fetch;

    await useStore.getState().createCell("p1", { kind: "markdown", after_cell_id: "missing-id", body: "" });
    expect(useStore.getState().cellsByProject.p1.map((c) => c.id)).toEqual(["A", "B", "C", "NEW"]);
  });

  it("deleteProject leaves activeProjectId alone when a non-active project is deleted", async () => {
    const { useStore } = await import("./store");
    useStore.setState({
      projects: [
        { id: "p1", name: "P1", created_at: "", updated_at: "" },
        { id: "p2", name: "P2", created_at: "", updated_at: "" },
      ],
      activeProjectId: "p2",
      cellsByProject: {},
    });
    globalThis.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 })) as typeof fetch;
    await useStore.getState().deleteProject("p1");
    expect(useStore.getState().activeProjectId).toBe("p2");
  });
});
