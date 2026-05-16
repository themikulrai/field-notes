import { useState } from "react";
import { setApiKey } from "../lib/api";

export function KeyGate() {
  const [val, setVal] = useState("");
  return (
    <div className="key-gate-page">
      <div className="key-gate-card">
        <h2>Field Notes</h2>
        <p className="mono">Enter your Field Notes key to begin.</p>
        <input
          type="password"
          autoFocus
          placeholder="X-Field-Notes-Key"
          value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && val.trim()) {
              setApiKey(val.trim());
              window.location.reload();
            }
          }}
        />
        <button
          type="button"
          onClick={() => {
            if (!val.trim()) return;
            setApiKey(val.trim());
            window.location.reload();
          }}
        >
          save & reload
        </button>
      </div>
    </div>
  );
}
