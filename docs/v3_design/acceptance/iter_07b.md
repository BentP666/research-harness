# Iter 07b 验收报告

## 自检
- [x] 后端 pytest 全绿（80 passed — 3 new matrix tests）
- [x] 前端 vitest 全绿（17 passed）
- [x] 手动验证通过

## 文件变更

| 文件 | 操作 |
|------|------|
| `packages/research_harness/migrations/062_experiment_matrix.sql` | 新建 |
| `packages/research_harness/research_harness/primitives/experiment_matrix_impl.py` | 新建 |
| `packages/research_harness_mcp/research_harness_mcp/http_api.py` | 3 endpoints |
| `packages/research_harness_mcp/tests/test_experiment_matrix.py` | 3 tests |
| `web/src/components/topic/method-atoms-library.tsx` | 新建 |
| `web/src/components/topic/experiment-matrix-card.tsx` | 新建 |
| `web/src/lib/api.ts` | MatrixCell type + 3 functions |
| `web/src/app/topics/[id]/page.tsx` | 2-column layout for atoms+matrix |
| `web/src/locales/en.json` | atoms.* + matrix.* keys |
| `web/src/locales/zh.json` | atoms.* + matrix.* keys |

## 4 态
- MethodAtomsLibrary: empty/loading/error/success (grouped by atom_type)
- ExperimentMatrixCard: empty/loading/error/success (grid with status colors)

## 已知问题
- 无
