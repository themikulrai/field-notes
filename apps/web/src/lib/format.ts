// Shared formatting helpers.

export function fmtAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const m = Math.max(1, Math.round((Date.now() - t) / 60_000));
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

export const STATUSES = {
  in_progress: {
    label: "in progress",
    short: "running",
    color: "var(--c-amber)",
    bg: "var(--c-amber-bg)",
    rail: "var(--c-amber)",
    dotAnim: true,
  },
  open: {
    label: "open",
    short: "needs review",
    color: "var(--c-blue)",
    bg: "var(--c-blue-bg)",
    rail: "var(--c-blue)",
    dotAnim: false,
  },
  verified: {
    label: "verified",
    short: "verified",
    color: "var(--c-green)",
    bg: "var(--c-green-bg)",
    rail: "var(--c-green)",
    dotAnim: false,
  },
  rejected: {
    label: "rejected",
    short: "rejected",
    color: "var(--c-red)",
    bg: "var(--c-red-bg)",
    rail: "var(--c-red)",
    dotAnim: false,
  },
} as const;

export const STATUS_ORDER = ["in_progress", "open", "verified", "rejected"] as const;

export type StatusMeta = (typeof STATUSES)[keyof typeof STATUSES];

// Resolve a cell's status to its display metadata, tolerating any value the
// backend might send that this build doesn't know about (e.g. the deprecated
// "ready", or a future status added server-side before the web app catches
// up). Returns the "open" style as a safe default so an unknown status renders
// as "needs review" instead of throwing and white-screening the whole app.
export function statusMeta(status: string | null | undefined): StatusMeta {
  if (status && Object.prototype.hasOwnProperty.call(STATUSES, status)) {
    return STATUSES[status as keyof typeof STATUSES];
  }
  return STATUSES.open;
}
