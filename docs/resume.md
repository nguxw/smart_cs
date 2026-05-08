# Resume Bullets

- 设计并实现 SmartCS Agent Desk，一个电商售后多Agent智能客服系统，基于 Python/FastAPI 和 LangGraph-style workflow 编排意图识别、RAG检索、业务工具调用、工单升级、合规审查与流式回复。
- 抽象 OpenAI-compatible/Ollama/Mock `LLMProvider`，支持云模型与本地兜底；工具层采用 MCP-style schema 暴露订单查询、退款资格校验、退款创建、发票查询和人工工单能力。
- 接入 PostgreSQL、Redis、Qdrant 真实数据层：PostgreSQL 持久化业务数据与 Agent trace，Redis 管理短期会话、SSE流状态与限流，Qdrant 承载知识库向量检索。
- 构建 Agent Harness 评测体系，覆盖约120条合成售后样例，自动统计意图准确率、工具调用正确率、引用命中率、PII泄露率和端到端延迟，并接入 CI 回归。
- 开发 React 控制台展示聊天、Agent轨迹、工具调用、知识引用、工单队列、知识库检索和评测报告，配套 Docker Compose 启动 API、前端、PostgreSQL、Redis、Qdrant、Jaeger、Prometheus 与 Grafana。
