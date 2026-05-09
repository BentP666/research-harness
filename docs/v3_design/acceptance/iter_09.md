# Iter 09 验收报告

## 自检
- [x] 后端 pytest 全绿（77 passed in 5.89s — 含 6 个新测试）
- [x] 前端单元测试 — N/A
- [x] Playwright E2E — N/A
- [x] 手动验证通过

## 测试覆盖 (6 tests)
- test_search_without_retrieval_fields_no_log — 老调用方不写 log
- test_search_with_retrieval_fields_writes_log — 三字段齐全时写 log
- test_search_invalid_reason_no_log — 非法 reason 静默忽略
- test_get_retrieval_log — GET 返回条目
- test_get_retrieval_log_404_missing_topic — 不存在 topic 返回 404
- test_all_five_reasons_writable — 5 种 trigger_reason 全部可写入

## 兼容性验证
- PaperSearchRequest 新增 stage + trigger_reason 字段均为 Optional
- 老调用方（expansion 流程、前端现有搜索）无需修改
- _search_papers_impl 内部函数完全不动

## 文件变更

| 文件 | 操作 |
|------|------|
| `packages/research_harness/migrations/061_retrieval_log.sql` | 新建 |
| `packages/research_harness_mcp/research_harness_mcp/http_api.py` | 扩展 PaperSearchRequest + 新增 GET retrieval-log |
| `packages/research_harness_mcp/tests/test_retrieval_log.py` | 新建 6 个测试 |

## 已知问题
- 无
