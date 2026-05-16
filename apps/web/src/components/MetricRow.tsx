import type { MetricItem } from "../lib/types";

export function MetricRow({ items }: { items: MetricItem[] }) {
  return (
    <div className="metrics">
      {items.map((m, i) => (
        <div className="metric" key={`${m.k}-${i}`}>
          <div className="metric-k">{m.k}</div>
          <div className="metric-v">{m.v}</div>
          {m.d && <div className="metric-d">{m.d}</div>}
        </div>
      ))}
    </div>
  );
}
