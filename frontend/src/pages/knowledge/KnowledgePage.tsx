import { FilePlus2, FileSearch, Lightbulb } from "lucide-react";
import type { FormEvent } from "react";

import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import type { Citation } from "../../types/api";
import { CATEGORY_OPTIONS } from "../../shared/demoData";
import { formatScore } from "../../shared/format";

type KnowledgeForm = {
  title: string;
  source: string;
  category: string;
  tags: string;
  content: string;
};

export function KnowledgePage({
  query,
  setQuery,
  category,
  setCategory,
  results,
  busy,
  form,
  setForm,
  onSearch,
  onIngest
}: {
  query: string;
  setQuery: (query: string) => void;
  category: string;
  setCategory: (category: string) => void;
  results: Citation[];
  busy: boolean;
  form: KnowledgeForm;
  setForm: (updater: (form: KnowledgeForm) => KnowledgeForm) => void;
  onSearch: (event?: FormEvent) => Promise<void>;
  onIngest: (event: FormEvent) => Promise<number | undefined>;
}) {
  const lowConfidence = results.filter((doc) => (doc.grounding_score ?? 0) < 0.15);
  return (
    <section className="knowledge-ops-grid">
      <Card className="knowledge-search">
        <div className="panel-head compact">
          <FileSearch />
          <h2>知识检索</h2>
        </div>
        <form className="search-row" onSubmit={onSearch}>
          <label htmlFor="kb-input">检索</label>
          <input id="kb-input" value={query} onChange={(event) => setQuery(event.target.value)} />
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">全部分类</option>
            {CATEGORY_OPTIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <Button type="submit" disabled={busy}>
            搜索
          </Button>
        </form>
        <div className="kb-results">
          {results.map((doc) => (
            <article key={doc.id} className="kb-card">
              <div>
                <strong>{doc.title}</strong>
                <span>
                  {doc.category} / v{doc.version ?? 1} / {doc.status ?? "published"} / score{" "}
                  {formatScore(doc.score)}
                </span>
              </div>
              <p>{doc.content}</p>
            </article>
          ))}
          {results.length === 0 && <EmptyState text="暂无检索结果" />}
        </div>
      </Card>

      <Card title="知识文档" icon={<FileSearch />} className="knowledge-docs">
        <div className="doc-table">
          {results.slice(0, 6).map((doc) => (
            <div key={`doc-${doc.id}`} className="doc-row">
              <strong>{doc.source}</strong>
              <span>{doc.category}</span>
              <em>{doc.status ?? "published"}</em>
              <b>v{doc.version ?? 1}</b>
            </div>
          ))}
          {results.length === 0 && <EmptyState text="先检索或导入知识文档" />}
        </div>
      </Card>

      <Card title="知识导入" icon={<FilePlus2 />} className="knowledge-ingest">
        <form className="operation-form knowledge-editor" onSubmit={onIngest}>
          <label>
            <span>标题</span>
            <input value={form.title} onChange={(event) => setForm((item) => ({ ...item, title: event.target.value }))} />
          </label>
          <div className="form-grid">
            <label>
              <span>分类</span>
              <select value={form.category} onChange={(event) => setForm((item) => ({ ...item, category: event.target.value }))}>
                {CATEGORY_OPTIONS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>来源</span>
              <input value={form.source} onChange={(event) => setForm((item) => ({ ...item, source: event.target.value }))} />
            </label>
          </div>
          <label>
            <span>标签</span>
            <input value={form.tags} onChange={(event) => setForm((item) => ({ ...item, tags: event.target.value }))} />
          </label>
          <label>
            <span>内容</span>
            <textarea value={form.content} onChange={(event) => setForm((item) => ({ ...item, content: event.target.value }))} />
          </label>
          <div className="form-footer">
            <Button type="submit" disabled={busy || !form.title || !form.content}>
              写入知识库
            </Button>
          </div>
        </form>
      </Card>

      <Card title="知识反馈" icon={<Lightbulb />} className="knowledge-feedback">
        <div className="feedback-list">
          {lowConfidence.map((doc) => (
            <div key={`feedback-${doc.id}`} className="feedback-row">
              <strong>低置信命中</strong>
              <span>{doc.title}</span>
              <p>建议人工复核切分、标题或补充 FAQ。</p>
            </div>
          ))}
          {lowConfidence.length === 0 && <EmptyState text="暂无未命中或低置信反馈" />}
        </div>
      </Card>
    </section>
  );
}
