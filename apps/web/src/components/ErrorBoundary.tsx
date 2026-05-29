// Catch-all render guard. Before this existed, ANY uncaught error thrown while
// rendering a cell (e.g. an unknown status hitting STATUSES[status] -> reading
// .rail on undefined) unmounted the entire React tree and left a blank white
// page. This boundary converts that into a visible, recoverable error panel so
// one bad cell can never take the whole site down again.

import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Surface it in the console for debugging; the panel below is the user UI.
    // eslint-disable-next-line no-console
    console.error("Field Notes render error:", error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    return (
      <div className="page" role="alert">
        <div className="empty-create-page">
          <div className="mono" style={{ fontWeight: 600 }}>
            Something broke while rendering this view.
          </div>
          <div className="mono dim" style={{ maxWidth: 560, overflowWrap: "anywhere" }}>
            {error.message || String(error)}
          </div>
          <button type="button" onClick={() => this.setState({ error: null })}>
            try again
          </button>
          <button type="button" onClick={() => window.location.reload()}>
            reload
          </button>
        </div>
      </div>
    );
  }
}
