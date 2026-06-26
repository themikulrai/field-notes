// TypeScript mirrors of packages/schema/field_notes_schema/__init__.py.
// Match the API JSON shape exactly: a single Cell type with optional fields
// for all kinds (agent | markdown | empty), like Pydantic's CellRead.

export type CellStatus = "in_progress" | "open" | "verified" | "rejected";
export type CellKind = "agent" | "markdown" | "empty";
export type VerdictState = "accept" | "reject";

export interface Verdict {
  state: VerdictState;
  note: string;
  by: string;
  at: string; // ISO datetime
}

export interface MetricItem {
  k: string;
  v: string;
  d?: string | null;
}

export interface VisualData {
  kind: "data";
  chart: "line" | "sweep" | "bar";
  series: Array<Record<string, unknown>>;
}

export interface VisualVega {
  kind: "vega";
  spec: Record<string, unknown>;
}

export interface VisualSvg {
  kind: "svg";
  source: string;
}

export interface VisualSandbox {
  kind: "sandbox";
  html: string;
  js: string;
  css: string;
}

export type Visual = VisualData | VisualVega | VisualSvg | VisualSandbox;

export interface VideoSlot {
  label: string;
  duration: string;
  url?: string | null;
  mime?: string | null;
}

export interface DeepBlock {
  hparams: Record<string, string>;
  files: string[];
  runs: Array<{ name: string; url: string }>;
  logs: string;
  // "not applicable" — set by agents on cells with genuinely no hparams/runs.
  na?: boolean;
}

export interface ProjectCounts {
  in_progress: number;
  open: number;
  verified: number;
  rejected: number;
}

export interface Project {
  id: string;
  name: string;
  subtitle?: string | null;
  repo?: string | null;
  created_at: string;
  updated_at: string;
  ui_filter?: "all" | CellStatus | null;
  counts?: ProjectCounts;
}

export interface Cell {
  id: string;
  project_id: string;
  kind: CellKind;
  position: number;
  created_at: string;
  updated_at: string;
  title?: string | null;
  agent_id?: string | null;
  status?: CellStatus | null;
  conclusion?: string | null;
  metrics?: MetricItem[] | null;
  visual?: Visual | null;
  video?: VideoSlot | null;
  deep?: DeepBlock | null;
  verdict?: Verdict | null;
  locked: boolean;
  body?: string | null;
}

// Write-side payloads -------------------------------------------------------

export interface ProjectCreate {
  name: string;
  subtitle?: string | null;
  repo?: string | null;
}
export interface ProjectUpdate {
  name?: string | null;
  subtitle?: string | null;
  repo?: string | null;
}

export interface CellCreate {
  kind: CellKind;
  after_cell_id?: string | null;
  title?: string | null;
  agent_id?: string | null;
  status?: CellStatus | null;
  conclusion?: string | null;
  metrics?: MetricItem[] | null;
  visual?: Visual | null;
  video?: VideoSlot | null;
  deep?: DeepBlock | null;
  body?: string | null;
}

export interface CellUpdate {
  title?: string | null;
  agent_id?: string | null;
  status?: CellStatus | null;
  conclusion?: string | null;
  metrics?: MetricItem[] | null;
  visual?: Visual | null;
  video?: VideoSlot | null;
  deep?: DeepBlock | null;
  body?: string | null;
}

export interface VerdictSet {
  state: VerdictState;
  note?: string;
}

export interface ReorderRequest {
  direction?: "up" | "down" | null;
  position?: number | null;
}

export interface EventEnvelope {
  id: string;
  at: string;
  kind: string;
  project_id?: string | null;
  cell_id?: string | null;
  payload: Record<string, unknown>;
}
