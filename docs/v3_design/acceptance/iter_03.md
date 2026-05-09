# Iter 03 验收报告

## 自检
- [x] 后端 pytest 全绿（54 passed in 4.34s — 含 8 个新 field_brief 测试）
- [x] 前端单元测试 — N/A（本轮无前端变更）
- [x] Playwright E2E — N/A（本轮无前端变更）
- [x] 手动 dev 环境验证 — 见下方 curl 测试

## 测试覆盖
- test_build_returns_valid_schema — POST 返回有效 FieldBrief JSON
- test_build_writes_artifact — project_artifacts 有记录
- test_build_writes_meta — field_brief_meta 有记录
- test_get_returns_latest — GET 返回 brief + meta
- test_get_returns_null_when_no_brief — 无 brief 时返回 null
- test_invalid_llm_output_raises_500 — 无效 LLM 输出返回 500
- test_stale_flag_after_paper_ingest — 论文增长 >15% 触发 stale
- test_stale_flag_after_21_days — 超过 21 天触发 stale

## 文件变更

| 文件 | 操作 |
|------|------|
| `packages/research_harness/migrations/058_field_brief_meta.sql` | 新建 |
| `packages/research_harness/research_harness/primitives/field_brief_impl.py` | 新建 |
| `packages/research_harness_mcp/research_harness_mcp/http_api.py` | 新增 POST/GET field-brief 端点 + paper ingest stale 检查 |
| `packages/research_harness_mcp/tests/test_field_brief.py` | 新建 8 个测试 |

## 设计决策
- transient retry: 1 次重试仅针对 ConnectionError/TimeoutError/5xx，pydantic ValidationError 不重试
- FieldBrief pydantic schema 含 Literal 枚举校验，LLM 输出必须严格匹配
- 21 天 + 15% 论文增长双重 stale 检测

## 已知问题
- 无
