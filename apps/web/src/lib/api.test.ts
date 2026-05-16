import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const ORIG_FETCH = globalThis.fetch;

describe("api client", () => {
  beforeEach(() => {
    localStorage.setItem("field-notes-key", "test-key");
    vi.resetModules();
  });
  afterEach(() => {
    localStorage.clear();
    globalThis.fetch = ORIG_FETCH;
  });

  it("listProjects sends GET with X-Field-Notes-Key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "p1", name: "X", created_at: "", updated_at: "" }]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock as typeof fetch;
    const mod = await import("./api");
    const res = await mod.listProjects();
    expect(res).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/projects$/);
    expect(init?.method).toBe("GET");
    expect(init?.headers).toMatchObject({ "X-Field-Notes-Key": "test-key" });
  });

  it("createProject sends POST with JSON body + content-type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "p2", name: "new", created_at: "", updated_at: "" }), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock as typeof fetch;
    const mod = await import("./api");
    await mod.createProject({ name: "new" });
    const [, init] = fetchMock.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(JSON.parse((init?.body as string) || "{}")).toEqual({ name: "new" });
    expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
  });

  it("setVerdict sends POST with state+note", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "c1" }), { status: 200, headers: { "content-type": "application/json" } }),
    );
    globalThis.fetch = fetchMock as typeof fetch;
    const mod = await import("./api");
    await mod.setVerdict("c1", { state: "accept", note: "looks good" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/cells/c1/verdict");
    expect(init?.method).toBe("POST");
    expect(JSON.parse((init?.body as string) || "{}")).toEqual({ state: "accept", note: "looks good" });
  });

  it("delete returns void on 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    globalThis.fetch = fetchMock as typeof fetch;
    const mod = await import("./api");
    await expect(mod.deleteCell("c1")).resolves.toBeUndefined();
  });

  it("throws ApiError on non-2xx with body detail", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "nope" }), {
        status: 409,
        headers: { "content-type": "application/json" },
      }),
    );
    globalThis.fetch = fetchMock as typeof fetch;
    const mod = await import("./api");
    await expect(mod.lockCell("c1")).rejects.toThrow(/nope/);
  });

  it("setApiKey writes to localStorage and is read back", async () => {
    const mod = await import("./api");
    mod.setApiKey("hello");
    expect(localStorage.getItem("field-notes-key")).toBe("hello");
    expect(mod.getApiKey()).toBe("hello");
  });
});
