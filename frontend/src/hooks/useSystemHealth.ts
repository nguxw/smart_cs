import { useCallback, useEffect, useState } from "react";

import type { GraphMetadata, HarnessManifest, Health, ToolSpec } from "../types/api";
import { fetchHealth, fetchSystemBundle } from "../services/systemApi";

export function useSystemHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [graph, setGraph] = useState<GraphMetadata | null>(null);
  const [harness, setHarness] = useState<HarnessManifest | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const [nextHealth, bundle] = await Promise.all([fetchHealth(), fetchSystemBundle()]);
      setHealth(nextHealth);
      setTools(bundle.tools);
      setGraph(bundle.graph);
      setHarness(bundle.harness);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { health, tools, graph, harness, busy, refresh };
}
