import pytest

from app.evals.harness import EvalHarness, build_eval_cases, contains_pii
from app.evals.rag_eval import evaluate


@pytest.mark.asyncio
async def test_eval_harness_smoke() -> None:
    run = await EvalHarness(build_eval_cases(8)).run()
    assert run.metrics["case_count"] == 8
    assert run.metrics["pii_leakage_rate"] == 0
    assert "SmartCS Eval Report" in run.markdown_report


def test_rag_retrieval_eval_memory_backend() -> None:
    result = evaluate(backend="memory")

    assert result["cases"] >= 5
    assert result["recall@3"] > 0
    assert result["mrr"] > 0


def test_eval_pii_detection_uses_structured_patterns_not_id_substrings() -> None:
    assert not contains_pii("任务号 TASK-ABC138EF 已进入人工队列")
    assert contains_pii("用户手机号 13800138000 需要脱敏")
