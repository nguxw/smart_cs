import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Ticket, TicketThread } from "../types/api";
import { fetchTicketThread, fetchTickets, updateTicket } from "../services/ticketsApi";

export function useTickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const selectedTicketIdRef = useRef<string | null>(null);
  const [thread, setThread] = useState<TicketThread | null>(null);
  const [busy, setBusy] = useState(false);
  const [threadBusy, setThreadBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadThread = useCallback(async (ticketId: string | null) => {
    if (!ticketId) {
      setThread(null);
      return null;
    }
    setThreadBusy(true);
    setError(null);
    try {
      const nextThread = await fetchTicketThread(ticketId);
      setThread(nextThread);
      return nextThread;
    } catch (cause) {
      if (cause instanceof Error && cause.message.startsWith("404 ")) {
        setThread(null);
        return null;
      }
      setError(cause instanceof Error ? cause.message : "工单会话加载失败");
      throw cause;
    } finally {
      setThreadBusy(false);
    }
  }, []);

  const selectTicket = useCallback(
    (ticketId: string) => {
      selectedTicketIdRef.current = ticketId;
      setSelectedTicketId(ticketId);
      void loadThread(ticketId).catch(() => undefined);
    },
    [loadThread]
  );

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const rows = await fetchTickets();
      const current = selectedTicketIdRef.current;
      const nextSelectedId = rows.some((ticket) => ticket.id === current)
        ? current
        : rows[0]?.id ?? null;
      selectedTicketIdRef.current = nextSelectedId;
      setTickets(rows);
      setSelectedTicketId(nextSelectedId);
      await loadThread(nextSelectedId);
      return rows;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "工单刷新失败");
      throw cause;
    } finally {
      setBusy(false);
    }
  }, [loadThread]);

  useEffect(() => {
    void refresh().catch(() => undefined);
  }, [refresh]);

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedTicketId) ?? tickets[0] ?? null,
    [selectedTicketId, tickets]
  );

  const stats = useMemo(() => {
    const open = tickets.filter((ticket) => ticket.status !== "resolved").length;
    const high = tickets.filter(
      (ticket) => ticket.priority === "high" && ticket.status !== "resolved"
    ).length;
    const pending = tickets.filter((ticket) => ticket.status === "pending").length;
    const resolved = tickets.filter((ticket) => ticket.status === "resolved").length;
    return { open, high, pending, resolved, total: tickets.length };
  }, [tickets]);

  const saveTicket = useCallback(
    async (ticketId: string, payload: Partial<Ticket>) => {
      setBusy(true);
      setError(null);
      try {
        const updated = await updateTicket(ticketId, payload);
        await refresh();
        selectedTicketIdRef.current = updated.id;
        setSelectedTicketId(updated.id);
        await loadThread(updated.id);
        return updated;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "工单保存失败");
        throw cause;
      } finally {
        setBusy(false);
      }
    },
    [loadThread, refresh]
  );

  const refreshThread = useCallback(
    () => loadThread(selectedTicketIdRef.current),
    [loadThread]
  );

  return {
    tickets,
    selectedTicket,
    selectedTicketId,
    setSelectedTicketId: selectTicket,
    thread,
    threadBusy,
    stats,
    busy,
    error,
    refresh,
    refreshThread,
    saveTicket
  };
}
