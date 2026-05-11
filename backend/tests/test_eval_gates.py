from __future__ import annotations

from pathlib import Path

import pytest

from app.evals.harness import EvalHarness, load_eval_cases


@pytest.mark.asyncio
async def test_agent_eval_release_gates() -> None:
    cases = load_eval_cases()
    assert len(cases) >= 50

    run = await EvalHarness(cases).run()
    metrics = run.metrics
    thresholds = metrics["thresholds"]

    assert metrics["intent_accuracy"] >= thresholds["intent_accuracy"]
    assert metrics["tool_accuracy"] >= thresholds["tool_accuracy"]
    assert metrics["tool_argument_accuracy"] >= thresholds["tool_argument_accuracy"]
    assert metrics["missing_slot_accuracy"] >= thresholds["missing_slot_accuracy"]
    assert metrics["forbidden_tool_violation_rate"] == thresholds["forbidden_tool_violation_rate"]
    assert metrics["citation_hit_rate"] >= thresholds["citation_hit_rate"]
    assert metrics["groundedness"] >= thresholds["groundedness"]
    assert metrics["pii_leakage_rate"] == thresholds["pii_leakage_rate"]
    assert metrics["handoff_precision"] >= thresholds["handoff_precision"]
    assert metrics["task_success_rate"] >= thresholds["task_success_rate"]
    assert metrics["latency_p95_ms"] <= thresholds["end_to_end_p95_ms"]

    report_dir = Path(__file__).resolve().parents[1] / "reports"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "eval_report.md").write_text(run.markdown_report, encoding="utf-8")
