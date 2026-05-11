# Service Integration

The integration workflow proves that the local service stack is more than a Compose template.

## Covered Services

| Service | Evidence |
| --- | --- |
| PostgreSQL | Conversation, case, task, refund, and tool-audit records persist through the repository adapter. |
| Redis | Short memory and stream-event state are written and read through `RedisRuntimeService`. |
| Qdrant | A knowledge document is ingested, embedded, and retrieved with category filtering. |
| Agent runtime | A refund request creates a pending confirmation task, confirmation executes `create_refund`, and repeated confirmation does not duplicate the refund. |

## Local Run

```powershell
docker compose up -d postgres redis qdrant
$env:SMARTCS_RUN_INTEGRATION="1"
.\.conda\python.exe -m pytest backend\tests\integration -q
```

The default local pytest run skips these tests unless `SMARTCS_RUN_INTEGRATION=1` is set, because they require running service containers.
