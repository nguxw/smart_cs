# Resume Bullets

- 设计并实现 SmartCS CaseOps，一个电商售后 Agentic Customer Support Platform，基于 Python/FastAPI 和 LangGraph-style 状态图编排意图识别、Case/Task 绑定、RAG 检索、工具策略、人工确认、人工接管、合规审查与流式回复。
- 抽象开发态 `AuthContext`、`ToolRuntime`、`ToolPolicy` 和 `ToolAuditLog`，将高风险 `create_refund` 从直接执行改为“资格校验 -> pending confirmation Task -> 用户确认 -> 幂等执行 -> 审计落库”。
- 接入 PostgreSQL、Redis、Qdrant 真实数据层：PostgreSQL 持久化订单、退款、工单、Case、Task、工具审计与 Agent trace，Redis 管理短期会话、SSE流状态与限流，Qdrant 承载可插拔 embedding、rerank 和 grounding 的知识检索。
- 构建分类 Agent Regression 评测体系，覆盖 intent、tool call、tool argument、RAG grounding、safety、multi-turn、human handoff，统计意图准确率、工具参数准确率、引用命中率、groundedness、handoff precision、task success、PII泄露率和端到端延迟。
- 重构 React 控制台为坐席工作台、工单队列、知识运营、发布门禁和 AgentOps 五个产品页，配套 Docker Compose 启动 API、前端、PostgreSQL、Redis、Qdrant、Jaeger、Prometheus 与 Grafana。
