import { useCallback, useEffect, useMemo, useState } from "react";

import type { Ticket } from "../types/api";
import { fetchTickets, updateTicket } from "../services/ticketsApi";

export function useTickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const rows = await fetchTickets();
    setTickets(rows);
    setSelectedTicketId((current) => current ?? rows[0]?.id ?? null);
  }, []);

  useEffect(() => {
    void refresh();
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
      try {
        const updated = await updateTicket(ticketId, payload);
        await refresh();
        setSelectedTicketId(updated.id);
        return updated;
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  return {
    tickets,
    selectedTicket,
    selectedTicketId,
    setSelectedTicketId,
    stats,
    busy,
    refresh,
    saveTicket
  };
}
