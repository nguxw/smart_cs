# Evaluation Release Gates

SmartCS treats agent behavior as a release surface. Prompt, tool, model, and KB changes must pass the fixed mock regression set before they are considered safe for the portfolio demo.

## Case Set

The current gate uses the unique JSONL fixtures in `backend/app/evals/cases/` rather than repeating cases to inflate the sample count. At the time of writing, the set contains 22 deterministic cases across intent routing, tool calls, tool arguments, missing slots, RAG grounding, safety, multi-turn behavior, and human handoff.

## Blocking Metrics

| Metric | Gate |
| --- | ---: |
| Intent accuracy | >= 90% |
| Tool accuracy | >= 90% |
| Tool argument accuracy | >= 90% |
| Missing slot accuracy | >= 90% |
| Forbidden tool violation rate | 0% |
| Citation hit rate | >= 85% |
| Groundedness | >= 80% |
| PII leakage rate | 0% |
| Handoff precision | >= 85% |
| Task success rate | >= 85% |

## Badcase Workflow

1. Reproduce the failing fixture with `pytest backend/tests/test_eval_gates.py -q`.
2. Identify whether the regression came from routing, planning, tool policy, KB retrieval, or answer composition.
3. Add or tighten a fixture before changing logic when the badcase represents a new requirement.
4. Rerun the full local check script before publishing the change.

CI uploads `backend/reports/eval_report.md` as the `smartcs-eval-report` artifact for each run.
