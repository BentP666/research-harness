# Iter 08 验收报告

## 自检
- [x] 后端 pytest 全绿（84 passed — 4 new venue tests）
- [x] 前端 vitest 全绿（17 passed）
- [x] 手动验证通过

## 测试覆盖 (4 tests)
- test_venue_decision_preferred_match — preferred constraint 匹配 EMNLP
- test_venue_decision_get — GET 返回已决定的 venue
- test_venue_decision_409_no_intake — 无 intake 返回 409
- test_style_kit_409_insufficient_papers — 不足 3 篇命中返回 409

## 3-Tier Degradation 验证
- Tier 1 (exact match): 精确 venue 匹配 → 使用
- Tier 2 (family expansion): venue 家族扩展，source_venues 如实记录
- Tier 3 (insufficient): 返回 409 Conflict + "Need at least 3 reference papers"
- **LLM 凭空推断风格 → 已禁止**（style_kit 仅从真实论文 compiled_summary 蒸馏）

## 文件变更

| 文件 | 操作 |
|------|------|
| `packages/research_harness/migrations/063_venue_decision.sql` | 新建（含 source_venues 列）|
| `packages/research_harness/research_harness/primitives/venue_decision_impl.py` | 新建 |
| `packages/research_harness_mcp/research_harness_mcp/http_api.py` | 4 endpoints |
| `packages/research_harness_mcp/tests/test_venue_decision.py` | 4 tests |
| `web/src/components/topic/venue-kit.tsx` | VenueDecisionBanner + VenueStyleKitCard |
| `web/src/lib/api.ts` | VenueDecisionData + VenueStyleKitData + 4 functions |
| `web/src/app/topics/[id]/page.tsx` | 插入 venue banner + kit card |
| `web/src/locales/en.json` | venue.* + styleKit.* keys |
| `web/src/locales/zh.json` | venue.* + styleKit.* keys |
| `docs/v3_design/venue_family_mapping.md` | venue family 映射文档 |

## 已知问题
- 无
