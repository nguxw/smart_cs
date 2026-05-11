import { Gauge, Play, ShieldCheck } from "lucide-react";

import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import type { EvalRun, HarnessManifest } from "../../types/api";
import { formatGateValue } from "../../shared/format";

export function EvalPage({
  harness,
  evalRun,
  evalSize,
  setEvalSize,
  busy,
  onRun
}: {
  harness: HarnessManifest | null;
  evalRun: EvalRun | null;
  evalSize: number;
  setEvalSize: (size: number) => void;
  busy: boolean;
  onRun: () => Promise<unknown>;
}) {
  const thresholds = (evalRun?.metrics.thresholds as Record<string, number> | undefined) ?? {};
  const failedCases = evalRun?.cases?.filter((row) => {
    return ["intent_ok", "tools_ok", "tool_arguments_ok", "citation_ok", "task_ok"].some(
      (key) => row[key] === false
    );
  });
  return (
    <section className="eval-center-grid">
      <Card className="eval-control">
        <div className="section-head compact-head">
          <div className="section-title">
            <span>
              <Gauge />
            </span>
            <div>
              <h2>发布门禁中心</h2>
              <p>每次 prompt、工具、知识或模型变更后，跑 Agent Regression。</p>
            </div>
          </div>
          <div className="eval-actions">
            <select value={evalSize} onChange={(event) => setEvalSize(Number(event.target.value))}>
              <option value={21}>21 dataset</option>
              <option value={60}>60 regression</option>
              <option value={120}>120 full</option>
            </select>
            <Button onClick={() => void onRun()} disabled={busy}>
              <Play size={17} />
              运行
            </Button>
          </div>
        </div>
        <div className="eval-grid">
          {evalRun ? (
            Object.entries(evalRun.metrics)
              .filter(([, value]) => typeof value !== "object")
              .map(([key, value]) => (
                <div key={key} className="eval-metric">
                  <span>{key}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))
          ) : (
            <div className="eval-empty">
              <Gauge size={34} />
              <strong>暂无评测报告</strong>
              <p>数据集已按 intent、tool、argument、RAG、safety、multi-turn、handoff 分类。</p>
            </div>
          )}
        </div>
      </Card>

      <Card title="Gate 状态" icon={<ShieldCheck />} className="eval-gates">
        <div className="gate-list">
          {Object.entries(harness?.release_gates ?? thresholds).map(([key, value]) => (
            <div key={key} className="gate-row">
              <span>{key}</span>
              <strong>{formatGateValue(key, value)}</strong>
            </div>
          ))}
        </div>
      </Card>

      <Card title="失败样本" icon={<Gauge />} className="failed-cases">
        <div className="failed-table">
          {(failedCases ?? []).slice(0, 12).map((row) => (
            <div key={String(row.id)} className="failed-row">
              <strong>{String(row.id)}</strong>
              <span>{String(row.actual_intent)} / {String(row.actual_tools)}</span>
              <p>{String(row.answer ?? "")}</p>
            </div>
          ))}
          {(!failedCases || failedCases.length === 0) && <p className="muted">当前无失败样本。</p>}
        </div>
      </Card>

      <pre className="report">{evalRun?.markdown_report ?? "Markdown report will appear here."}</pre>
    </section>
  );
}
