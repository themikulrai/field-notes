import { useState } from "react";
import type { DeepBlock } from "../lib/types";

export function DeepLayer({ deep }: { deep: DeepBlock }) {
  const [showAllLogs, setShowAllLogs] = useState(false);
  const logsLines = (deep.logs || "").split("\n");
  const logsShown = showAllLogs ? logsLines : logsLines.slice(0, 4);

  return (
    <div className="deep">
      <div className="deep-grid">
        <section className="deep-block">
          <h4 className="deep-h">hyperparameters</h4>
          <dl className="kv">
            {Object.entries(deep.hparams || {}).map(([k, v]) => (
              <div className="kv-row" key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="deep-block">
          <h4 className="deep-h">files</h4>
          <ul className="list">
            {(deep.files || []).map((f) => (
              <li key={f} className="list-row">
                <svg width="11" height="13" viewBox="0 0 11 13" aria-hidden="true">
                  <path d="M1 1h6l3 3v8H1z" fill="none" stroke="currentColor" strokeWidth="1" />
                </svg>
                <span className="mono">{f}</span>
              </li>
            ))}
            {(!deep.files || deep.files.length === 0) && <li className="dim mono">—</li>}
          </ul>
        </section>
        <section className="deep-block">
          <h4 className="deep-h">runs</h4>
          <ul className="list">
            {(deep.runs || []).map((r) => (
              <li key={r.name} className="list-row">
                <span className="run-dot" />
                <a className="mono link" href={r.url}>
                  {r.name}
                </a>
                <span className="mono dim run-url">{r.url.replace("wandb://", "")}</span>
              </li>
            ))}
            {(!deep.runs || deep.runs.length === 0) && (
              <li className="dim mono">no runs linked</li>
            )}
          </ul>
        </section>
      </div>
      <section className="deep-block">
        <h4 className="deep-h">
          raw logs
          {logsLines.length > 4 && (
            <button className="link-btn" onClick={() => setShowAllLogs((v) => !v)}>
              {showAllLogs ? "collapse" : `show all (${logsLines.length})`}
            </button>
          )}
        </h4>
        <pre className="logs mono">
          {logsShown.join("\n")}
          {!showAllLogs && logsLines.length > 4 && "\n…"}
        </pre>
      </section>
    </div>
  );
}
