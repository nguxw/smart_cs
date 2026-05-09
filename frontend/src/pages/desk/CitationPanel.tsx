import { FileSearch } from "lucide-react";

import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import type { Citation } from "../../types/api";
import { formatScore } from "../../shared/format";

export function CitationPanel({ citations }: { citations: Citation[] }) {
  return (
    <Card title="知识证据" icon={<FileSearch />}>
      <div className="citation-list">
        {citations.length === 0 && <EmptyState text="暂无知识库引用" />}
        {citations.map((doc) => (
          <article key={doc.id} className="citation-card">
            <div>
              <strong>{doc.title}</strong>
              <span>
                {doc.category} / {doc.source} / score {formatScore(doc.score)} / grounding{" "}
                {formatScore(doc.grounding_score)}
              </span>
            </div>
            <p>{doc.content.slice(0, 180)}</p>
          </article>
        ))}
      </div>
    </Card>
  );
}
