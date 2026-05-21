# RH Discovery evidence pipeline

Discovery 的首页可以只展示摘要，但底层证据必须可复查。当前门控是：

- 10 个 Discovery 顶层问题空间全部覆盖。
- 每个问题至少 100 条去重后的最新证据。
- “最新”默认定义为 `current_year - 1` 之后；本轮为 2025+。
- 每个问题必须同时覆盖 `rh_paper_search` 与 `provider_fanout` 两条采集路线。
- 路线执行不能有 provider error；否则验证失败。

## 运行

```bash
.venv/bin/python -m research_harness.cli discover evidence plan

.venv/bin/python -m research_harness.cli discover evidence collect \
  --output docs/discover/evidence/latest.json \
  --per-query-limit 50 \
  --min-per-problem 100 \
  --min-recent-per-problem 100

.venv/bin/python -m research_harness.cli discover evidence validate \
  docs/discover/evidence/latest.json
```

等价脚本入口：

```bash
PYTHONPATH=packages/research_harness \
  .venv/bin/python scripts/discovery_collect_evidence.py \
  --output docs/discover/evidence/latest.json
```

## 稳定性策略

默认启用稳定的公开 provider：

- `crossref`
- `openalex`

默认禁用容易拖慢批处理或触发限流的 provider：

- `arxiv`：可用 `RH_DISCOVER_EVIDENCE_ALLOW_ARXIV=1` 打开。
- Semantic Scholar free tier：配置 `S2_API_KEY` 或设置 `RH_DISCOVER_EVIDENCE_ALLOW_S2_FREE=1` 后打开。
- PASA：可用 `--include-pasa` 打开。

这样做的目的不是降低证据质量，而是保证 Discovery 的定期证据刷新不会因为无 key provider 限流而失败。需要更高召回时，优先配置 `S2_API_KEY`、`OPENREVIEW_ENABLE=1`、`GOOGLE_SCHOLAR_API_URL`。

## 当前 manifest

`latest.json` 是可验证的机器产物，不是手写摘要。验证命令会重新从 `records` 计算覆盖度，而不是信任 manifest 内嵌的 coverage 字段。
