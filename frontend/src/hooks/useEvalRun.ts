import { useState } from "react";

import type { EvalRun } from "../types/api";
import { runEval } from "../services/evalApi";

export function useEvalRun() {
  const [evalRun, setEvalRun] = useState<EvalRun | null>(null);
  const [evalSize, setEvalSize] = useState(120);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const body = await runEval(evalSize);
      setEvalRun(body);
      return body;
    } finally {
      setBusy(false);
    }
  }

  return { evalRun, evalSize, setEvalSize, busy, run };
}
