# Goal
测试 Research Harness 1.0 项目本体性能：CLI、MCP/API、核心 SQLite 数据库、ResearchFlowBench、Web 构建与关键页面渲染的上限与回归趋势。

说明：LongTask 只作为“任务承载/看板/手机审核”的编排外壳，不作为本次性能验收目标；不再评估 LongTask 调度器吞吐。

## Stop rules
1) 不允许上传、发布、推送、收费模型调用或破坏性动作。
2) 单任务执行超过 120 秒立即标记 blocked 并记录风险。
3) 指标统一落盘 `artifacts/perf_results.json`。
4) 如任一关键指标 p95 退化 30% 以上，立即暂停并等待人工复核。

## Tasks
1. [ ] 收集基准环境信息（Python/Node 版本、CPU 架构、内存、工作目录 git 提交）。
2. [ ] 初始化性能结果目录 `artifacts/perf`，建立统一 `metrics_schema`（time_ms, op, p50_ms, p95_ms, p99_ms, throughput_rps, memory_mb）。
3. [ ] 编写 `scripts/perf/runner.py`：统一计时、重试与 JSON 输出。
4. [ ] 设计 `scripts/perf/bench_cli.py`：对 `rh --help`、`rh config show`、`rh topic list`、`rh paper list` 进行冷启动/热启动计时。
5. [ ] 建立 CLI baseline 目标：p50 < 250ms，p95 < 1000ms。
6. [ ] 编写 `scripts/perf/bench_db.py`：对核心 RH SQLite 表执行 topics、papers、artifacts、provenance 查询基准。
7. [ ] 建立 DB 查询目标：核心只读查询 p95 < 150ms，并记录 1k/3k/5k 行规模快照。
8. [ ] 启动 MCP/API 到本地端口，压测健康检查、topics、papers、reports、discover 关键 GET 端点。
9. [ ] 编写 `scripts/perf/http_bench.py`：对关键 API 进行 60 次顺序请求与小并发请求，记录 p50/p95/p99。
10. [ ] 测试 ResearchFlowBench 输出形状与执行可复现性相关测试的耗时与失败率。
11. [ ] 运行 `pytest packages/research_harness/tests/test_researchflowbench_*`，记录总耗时、慢测试列表与失败率。
12. [ ] 运行核心 MCP/API 测试子集，记录耗时和慢用例。
13. [ ] 进行 Web 构建回归：运行 `npm run build`（3 次）记录 p50/p95 构建耗时和产物体积。
14. [ ] 运行 Web 关键页面测试（discover、topic prefill、longrun 页面只做 UI smoke），记录耗时和失败率。
15. [ ] 用本地浏览器或测试工具采样关键页面首屏可用时间：`/`, `/discovery`, `/library`, `/reports`, `/longrun`。
16. [ ] 汇总 CPU/内存峰值、磁盘增量与 cache/临时文件增长。
17. [ ] 对 LongTask 编排外壳只做最小 smoke：确认性能任务可在 `/longrun` 看板中显示并可产生人工 gate，不纳入性能评分。
18. [ ] 生成 `artifacts/perf/summary.md` 与 `artifacts/perf/perf_dashboard.json`（含回归告警）。
19. [ ] 形成回归结论：PASS/WAIVED/FAIL 与下轮优化优先级。
