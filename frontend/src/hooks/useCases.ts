import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { CaseTask, SupportCase, ToolAudit } from "../types/api";
import { fetchCaseDetail, fetchCases } from "../services/casesApi";

export type CaseDetail = {
  case: SupportCase;
  tasks: CaseTask[];
  audits: ToolAudit[];
};

export function useCases() {
  const [cases, setCases] = useState<SupportCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const selectedCaseIdRef = useRef<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = useCallback(async (caseId: string | null) => {
    if (!caseId) {
      setDetail(null);
      return null;
    }
    const nextDetail = await fetchCaseDetail(caseId);
    setDetail(nextDetail);
    return nextDetail;
  }, []);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const rows = await fetchCases();
      setCases(rows);
      const current = selectedCaseIdRef.current;
      const currentStillExists = rows.some((row) => row.id === current);
      const nextSelectedId = currentStillExists ? current : rows[0]?.id ?? null;
      selectedCaseIdRef.current = nextSelectedId;
      setSelectedCaseId(nextSelectedId);
      await loadDetail(nextSelectedId);
      return rows;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "服务案件刷新失败");
      throw cause;
    } finally {
      setBusy(false);
    }
  }, [loadDetail]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectCase = useCallback(
    async (caseId: string) => {
      selectedCaseIdRef.current = caseId;
      setSelectedCaseId(caseId);
      setBusy(true);
      setError(null);
      try {
        await loadDetail(caseId);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "服务案件详情加载失败");
      } finally {
        setBusy(false);
      }
    },
    [loadDetail]
  );

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? cases[0] ?? null,
    [cases, selectedCaseId]
  );

  const stats = useMemo(() => {
    const active = cases.filter((item) => !["resolved", "closed"].includes(item.status)).length;
    const waiting = cases.filter((item) => item.status === "waiting_customer").length;
    const handoff = cases.filter((item) => item.status === "handoff").length;
    const high = cases.filter(
      (item) => item.risk_level === "high" || item.priority === "high"
    ).length;
    const pendingTasks = detail?.tasks.filter((task) => task.status === "pending").length ?? 0;
    return { active, waiting, handoff, high, pendingTasks, total: cases.length };
  }, [cases, detail]);

  return {
    cases,
    selectedCase,
    selectedCaseId,
    detail,
    stats,
    busy,
    error,
    refresh,
    selectCase
  };
}
