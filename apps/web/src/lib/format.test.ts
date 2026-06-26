import { describe, it, expect } from "vitest";
import { statusMeta, STATUSES } from "./format";

describe("statusMeta", () => {
  it("returns the matching metadata for known statuses", () => {
    expect(statusMeta("verified")).toBe(STATUSES.verified);
    expect(statusMeta("rejected")).toBe(STATUSES.rejected);
    expect(statusMeta("open")).toBe(STATUSES.open);
  });

  it("falls back to 'open' for the deprecated/never-used statuses (ready, in_progress)", () => {
    expect(statusMeta("ready")).toBe(STATUSES.open);
    // in_progress is no longer a UI status; it degrades to the open presentation.
    expect(statusMeta("in_progress")).toBe(STATUSES.open);
  });

  it("falls back to 'open' for unknown / null / undefined", () => {
    expect(statusMeta("some_future_status")).toBe(STATUSES.open);
    expect(statusMeta(null)).toBe(STATUSES.open);
    expect(statusMeta(undefined)).toBe(STATUSES.open);
    expect(statusMeta("")).toBe(STATUSES.open);
  });

  it("does not resolve inherited Object.prototype keys", () => {
    // guards against e.g. statusMeta('toString') matching a prototype member
    expect(statusMeta("toString")).toBe(STATUSES.open);
    expect(statusMeta("hasOwnProperty")).toBe(STATUSES.open);
  });
});
