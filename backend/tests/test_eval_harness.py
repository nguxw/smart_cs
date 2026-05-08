import pytest

from app.evals.harness import EvalHarness, build_eval_cases


@pytest.mark.asyncio
async def test_eval_harness_smoke() -> None:
    run = await EvalHarness(build_eval_cases(8)).run()
    assert run.metrics["case_count"] == 8
    assert run.metrics["pii_leakage_rate"] == 0
    assert "SmartCS Eval Report" in run.markdown_report

