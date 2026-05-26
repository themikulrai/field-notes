// React hook that wires SSE -> store.applyEvent. One stream per active project.

import { useEffect } from "react";
import { openEventStream } from "./events";
import { useStore } from "./store";

export function useLiveEvents(): void {
  const activeProjectId = useStore((s) => s.activeProjectId);
  const applyEvent = useStore((s) => s.applyEvent);

  useEffect(() => {
    if (!activeProjectId) return;
    const seen = new Set<string>();
    const stream = openEventStream(activeProjectId, (env) => {
      // Resync sentinel: bus dropped events; refetch state from scratch.
      // No `id` on this envelope — must short-circuit before the dedup set.
      if (env.kind === "resync") {
        void useStore.getState().loadProjects();
        const pid = useStore.getState().activeProjectId;
        if (pid) void useStore.getState().loadCells(pid);
        return;
      }
      if (seen.has(env.id)) return;
      seen.add(env.id);
      if (seen.size > 200) {
        // bound the dedup set
        const first = seen.values().next().value;
        if (first) seen.delete(first);
      }
      void applyEvent(env);
    });
    return () => stream.close();
  }, [activeProjectId, applyEvent]);
}
