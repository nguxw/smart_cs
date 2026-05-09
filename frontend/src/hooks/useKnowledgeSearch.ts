import { FormEvent, useCallback, useEffect, useState } from "react";

import type { Citation } from "../types/api";
import { ingestKnowledge, searchKnowledge } from "../services/kbApi";

export function useKnowledgeSearch() {
  const [query, setQuery] = useState("7天无理由 物流超过48小时 电子发票 隐私");
  const [category, setCategory] = useState("");
  const [results, setResults] = useState<Citation[]>([]);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: "售后补偿规则补充",
    source: "manual-console.md",
    category: "refund",
    tags: "refund, compensation, after-sales",
    content:
      "当物流异常超过 48 小时且用户明确表达取消需求时，客服应先核验订单归属与物流状态；若未签收可优先引导拒收或创建售后工单，避免承诺即时退款。"
  });

  const search = useCallback(
    async (event?: FormEvent) => {
      event?.preventDefault();
      setBusy(true);
      try {
        setResults(await searchKnowledge(query, category));
      } finally {
        setBusy(false);
      }
    },
    [category, query]
  );

  const ingest = useCallback(
    async (event: FormEvent) => {
      event.preventDefault();
      setBusy(true);
      try {
        const body = await ingestKnowledge({
          title: form.title,
          content: form.content,
          source: form.source,
          category: form.category,
          tags: form.tags
            .split(/[,，]/)
            .map((tag) => tag.trim())
            .filter(Boolean)
        });
        setQuery(form.title);
        setResults(await searchKnowledge(form.title, form.category));
        return body.ingested_chunks;
      } finally {
        setBusy(false);
      }
    },
    [form]
  );

  useEffect(() => {
    void search();
  }, []);

  return {
    query,
    setQuery,
    category,
    setCategory,
    results,
    busy,
    form,
    setForm,
    search,
    ingest
  };
}
