// Dispatcher for the Visual discriminated union:
//   data   -> built-in SVG sparkline (line | sweep | bar)
//   vega   -> vega-embed dynamic import
//   svg    -> sanitized inline SVG
//   sandbox -> iframe srcdoc with bundled CDN libs

import { useEffect, useRef, useState } from "react";
import type { Visual, VisualData, VisualSandbox, VisualVega } from "../lib/types";
import { sanitizeSvg } from "../lib/markdown";

export function Sparkline({ visual }: { visual: Visual }) {
  if (visual.kind === "data") return <DataChart visual={visual} />;
  if (visual.kind === "vega") return <VegaChart visual={visual} />;
  if (visual.kind === "svg") return <SvgChart source={visual.source} />;
  return <SandboxChart visual={visual} />;
}

// --- "data" charts ---------------------------------------------------------

function DataChart({ visual }: { visual: VisualData }) {
  if (visual.chart === "line") return <LineChart series={visual.series} />;
  if (visual.chart === "sweep") return <SweepChart series={visual.series} />;
  return <BarChart series={visual.series} />;
}

function LineChart({ series }: { series: Array<Record<string, unknown>> }) {
  // Use the first series; series can also be just an array of {x,y}.
  const pts = normalizeXY(series);
  if (pts.length === 0) return placeholderChart();
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const xmin = Math.min(...xs);
  const xmax = Math.max(...xs);
  const ymin = Math.min(...ys);
  const ymax = Math.max(...ys);
  const sx = (x: number) =>
    32 + ((x - xmin) / Math.max(1e-9, xmax - xmin)) * (312 - 32);
  const sy = (y: number) =>
    92 - ((y - ymin) / Math.max(1e-9, ymax - ymin)) * (92 - 14);
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.x)} ${sy(p.y)}`).join(" ");

  return (
    <svg viewBox="0 0 320 110" className="chart">
      <defs>
        <linearGradient id="gloss-line" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--c-green)" stopOpacity="0.18" />
          <stop offset="100%" stopColor="var(--c-green)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <line x1="32" y1="92" x2="312" y2="92" stroke="var(--rule)" strokeWidth="1" />
      <line x1="32" y1="14" x2="32" y2="92" stroke="var(--rule)" strokeWidth="1" />
      <path d={path} fill="none" stroke="var(--c-green)" strokeWidth="2" />
      <path d={`${path} L 312 92 L 32 92 Z`} fill="url(#gloss-line)" />
    </svg>
  );
}

function SweepChart({ series }: { series: Array<Record<string, unknown>> }) {
  const pts = normalizeXY(series);
  if (pts.length === 0) return placeholderChart();
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const xmin = Math.min(...xs);
  const xmax = Math.max(...xs);
  const ymin = Math.min(...ys);
  const ymax = Math.max(...ys);
  const sx = (x: number) =>
    32 + ((x - xmin) / Math.max(1e-9, xmax - xmin)) * (312 - 32);
  const sy = (y: number) =>
    92 - ((y - ymin) / Math.max(1e-9, ymax - ymin)) * (92 - 14);
  const bestIdx = ys.indexOf(Math.max(...ys));
  const path = pts
    .map((p) => `${sx(p.x)} ${sy(p.y)}`)
    .map((s, i) => (i === 0 ? `M ${s}` : `L ${s}`))
    .join(" ");

  return (
    <svg viewBox="0 0 320 110" className="chart">
      <line x1="32" y1="92" x2="312" y2="92" stroke="var(--rule)" strokeWidth="1" />
      <line x1="32" y1="14" x2="32" y2="92" stroke="var(--rule)" strokeWidth="1" />
      <path d={path} fill="none" stroke="var(--c-blue)" strokeWidth="2" />
      {pts.map((p, i) => (
        <circle
          key={i}
          cx={sx(p.x)}
          cy={sy(p.y)}
          r={i === bestIdx ? 5 : 3.2}
          fill={i === bestIdx ? "var(--c-blue)" : "var(--paper)"}
          stroke="var(--c-blue)"
          strokeWidth="2"
        />
      ))}
    </svg>
  );
}

function BarChart({ series }: { series: Array<Record<string, unknown>> }) {
  const pts = normalizeXY(series);
  if (pts.length === 0) return placeholderChart();
  const ys = pts.map((p) => p.y);
  const ymax = Math.max(...ys, 1);
  const w = (312 - 32) / pts.length;
  return (
    <svg viewBox="0 0 320 110" className="chart">
      <line x1="32" y1="92" x2="312" y2="92" stroke="var(--rule)" strokeWidth="1" />
      <line x1="32" y1="14" x2="32" y2="92" stroke="var(--rule)" strokeWidth="1" />
      {pts.map((p, i) => {
        const h = (p.y / ymax) * (92 - 14);
        const x = 32 + i * w + 2;
        return (
          <rect
            key={i}
            x={x}
            y={92 - h}
            width={Math.max(2, w - 4)}
            height={h}
            fill="var(--c-blue)"
            opacity={0.7}
          />
        );
      })}
    </svg>
  );
}

function normalizeXY(series: Array<Record<string, unknown>>): Array<{ x: number; y: number }> {
  if (!Array.isArray(series) || series.length === 0) return [];
  // Each entry may be {x, y} OR {label, value} OR {step, loss}. Best-effort.
  return series
    .map((row, i) => {
      const x =
        toNumber(row.x) ?? toNumber(row.step) ?? toNumber(row.k) ?? i;
      const y =
        toNumber(row.y) ?? toNumber(row.value) ?? toNumber(row.v) ?? toNumber(row.loss) ?? 0;
      return { x, y };
    })
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
}
function toNumber(v: unknown): number | null {
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}
function placeholderChart() {
  return (
    <svg viewBox="0 0 320 110" className="chart">
      <line x1="32" y1="92" x2="312" y2="92" stroke="var(--rule)" strokeWidth="1" />
      <line x1="32" y1="14" x2="32" y2="92" stroke="var(--rule)" strokeWidth="1" />
      <text x="160" y="60" textAnchor="middle" className="chart-tick">
        no data
      </text>
    </svg>
  );
}

// --- "vega" ---------------------------------------------------------------

function VegaChart({ visual }: { visual: VisualVega }) {
  const ref = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mod = await import("vega-embed");
        if (cancelled || !ref.current) return;
        await mod.default(ref.current, visual.spec as object, {
          actions: false,
          theme: "dark",
        });
      } catch (e) {
        setErr((e as Error).message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [visual.spec]);
  if (err) return <div className="dim mono">vega error: {err}</div>;
  return <div className="vega-host" ref={ref} />;
}

// --- "svg" ----------------------------------------------------------------

function SvgChart({ source }: { source: string }) {
  const safe = sanitizeSvg(source);
  return <div className="svg-visual" dangerouslySetInnerHTML={{ __html: safe }} />;
}

// --- "sandbox" iframe -----------------------------------------------------

const SANDBOX_LIBS = [
  '<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js"></script>',
  '<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>',
  '<script src="https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.16/dist/plot.umd.min.js"></script>',
  '<script src="https://cdn.jsdelivr.net/npm/nouislider@15.8.1/dist/nouislider.min.js"></script>',
  '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.8.1/dist/nouislider.min.css" />',
].join("\n  ");

export function buildSandboxSrcdoc(visual: VisualSandbox): string {
  // Auto-postMessage height on load so the parent can size the iframe.
  const resizer = `
    const _post = () => parent.postMessage({type:'fn-resize', h: document.body.scrollHeight}, '*');
    window.addEventListener('load', _post);
    new ResizeObserver(_post).observe(document.body);
  `;
  return `<!doctype html>
<html><head>
  <style>${visual.css || ""}</style>
  ${SANDBOX_LIBS}
</head><body>${visual.html || ""}<script>${resizer}</script><script>${visual.js || ""}</script></body></html>`;
}

function SandboxChart({ visual }: { visual: VisualSandbox }) {
  const ref = useRef<HTMLIFrameElement>(null);
  const [h, setH] = useState(160);
  useEffect(() => {
    function onMsg(e: MessageEvent) {
      const data = e.data as { type?: string; h?: number };
      if (data && data.type === "fn-resize" && typeof data.h === "number") {
        setH(Math.min(1200, Math.max(80, data.h + 4)));
      }
    }
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, []);
  const srcdoc = buildSandboxSrcdoc(visual);
  return (
    <iframe
      ref={ref}
      className="sandbox-iframe"
      sandbox="allow-scripts"
      srcDoc={srcdoc}
      style={{ height: h }}
      title="sandbox visual"
    />
  );
}
