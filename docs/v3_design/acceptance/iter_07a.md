# Iter 07a 验收报告

## 自检
- [x] 后端 pytest 全绿（71 passed in 5.17s — 含 7 个新测试）
- [x] 前端单元测试 — N/A
- [x] Playwright E2E — N/A
- [x] 手动验证通过

## 测试覆盖 (7 tests)
- test_harvest_returns_summary — POST 返回 papers_processed + total_atoms
- test_harvest_writes_to_db — DB 写入 6 条含 6 种 atom_type
- test_list_atoms_all — GET 返回全部 atoms
- test_list_atoms_filtered — GET ?atom_type=loss 过滤
- test_delete_atom — DELETE 删除 + 数量减少
- test_harvest_batch_two_papers — 批量 2 篇 → 12 atoms
- test_harvest_empty_paper_ids_400 — 空列表返回 400

## 文件变更

| 文件 | 操作 |
|------|------|
| `packages/research_harness/migrations/060_method_atoms.sql` | 新建 |
| `packages/research_harness/research_harness/primitives/harvest_atoms_impl.py` | 新建 |
| `packages/research_harness_mcp/research_harness_mcp/http_api.py` | 新增 3 端点 |
| `packages/research_harness_mcp/tests/test_method_atoms.py` | 新建 7 个测试 |

## 已知问题
- 无
