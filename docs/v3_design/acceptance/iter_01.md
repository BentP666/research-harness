# Iter 01 验收报告

## 自检
- [x] 后端 pytest 全绿（46 passed in 3.79s — 包含 6 个新 intake_profile 测试）
- [x] 前端单元测试 — N/A（本轮无前端变更）
- [x] Playwright E2E — N/A（本轮无前端变更）
- [x] 手动 dev 环境点击通过

## curl 实测

```
PUT /api/topics/1/intake-profile → 200, 返回完整 profile JSON
GET /api/topics/1/intake-profile → 200, 返回同上
GET /api/topics/9999/intake-profile → 404
PUT invalid persona → 422 (pydantic validation)
```

## SQLite 验证

```
sqlite3 .research-harness/pool.db ".schema topic_intake_profile"
→ 表存在，含所有 CHECK 约束 + FK

sqlite3 ... "SELECT ... FROM project_artifacts WHERE artifact_type='intake_profile'"
→ stage='init', artifact_type='intake_profile' 记录存在
```

## 文件变更

| 文件 | 操作 |
|------|------|
| `packages/research_harness/migrations/057_intake_profile.sql` | 新建 |
| `packages/research_harness_mcp/research_harness_mcp/http_api.py` | 新增 IntakeProfileBody + GET/PUT 端点 |
| `packages/research_harness_mcp/tests/test_intake_profile.py` | 新建 6 个测试 |

## 与原 Plan 偏差

| 项 | Plan | 实际 | 原因 |
|----|------|------|------|
| 迁移编号 | 049 | 057 | 现有最大为 056 |
| 迁移目录 | `research_harness/data/migrations/` | `packages/research_harness/migrations/` | 实际代码路径 |
| 测试目录 | `research_harness_mcp/research_harness_mcp/tests/` | `packages/research_harness_mcp/tests/` | 实际代码路径 |
| record_artifact 参数 | `content=str` | `payload=dict` | 实际 OrchestratorService 签名 |

## 已知问题

- 无
