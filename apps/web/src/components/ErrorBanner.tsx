// Surface API errors as a dismissable banner at the top of the page.
// Special-cases 401 (invalid/missing API key) with a "reset key" affordance
// because that's the most common failure during initial setup.

import { useStore } from "../lib/store";
import { clearApiKey } from "../lib/api";

export function ErrorBanner() {
  const error = useStore((s) => s.error);
  const clearError = useStore((s) => s.clearError);
  if (!error) return null;

  const isAuth = /401|api[ -_]?key|invalid|unauthor/i.test(error);

  return (
    <div className="error-banner" role="alert">
      <div className="error-banner-body">
        <span className="error-banner-tag mono">ERROR</span>
        <span className="error-banner-msg">{error}</span>
        {isAuth && (
          <span className="error-banner-hint mono dim">
            — your X-Field-Notes-Key is missing or wrong. Click "reset key" then re-enter it.
          </span>
        )}
      </div>
      <div className="error-banner-actions">
        {isAuth && (
          <button
            type="button"
            className="ghost-btn mono"
            onClick={() => {
              clearApiKey();
              window.location.reload();
            }}
          >
            reset key
          </button>
        )}
        <button type="button" className="ghost-btn mono" onClick={clearError}>
          dismiss
        </button>
      </div>
    </div>
  );
}
