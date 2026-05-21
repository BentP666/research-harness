# Tool Gaps

> Agent 在科研过程中发现的缺失工具、Skill、Hook 或 MCP 功能。
> 格式：日期 + 场景 + 需求 + 优先级。定期审阅后转化为开发任务。

---

<!-- 示例条目 -->
<!-- ## 2026-04-08 批量 PDF 下载工具
**场景**: literature_mapping 阶段找到 30+ 论文，需要逐个下载 PDF
**需求**: 一个 skill 或 MCP 工具，输入 arxiv_id 列表，自动批量下载到 paper_library/
**优先级**: P1
-->

## 2026-04-27 paper_ingest --url silently lands meta_only [FIXED 2026-05-07]
**场景**: harness-doctrine Phase 1 — 想 ingest Anthropic 工程博客 URL（HTML，非 PDF）作为 doctrine source。
**现象**:
1. `rh paper ingest --url <blog-url>` 单独不够，必须搭 `--title` 或某个 id
2. 给了 title 后 ingest 成功，但 paper status = `meta_only`，HTML body 完全没抓
3. 后续 `claim_extract` / `paper_summarize` 没有 full text 可读
**修复**: 新增 `research_harness/acquisition/html_ingest.py`（stdlib-only HTML→markdown 解析器），`paper_ingest` 在收到 http(s) URL 且无 PDF 时自动 fetch，剥离 `<script>/<style>/<nav>` 后 upsert 为 `paper_annotations.section='summary'`，`papers.status` 从 `meta_only` 翻到 `text_only`，并把前 2000 字塞进 `abstract`。CLI 层也同步放宽了参数校验，允许 URL-only 入库。非 HTML content-type（如 application/pdf）不污染 annotation，而是返回 `html_ingest={"fetched": False, "reason": ...}` 让调用方 fall through 到 PDF pipeline。
**Regression**: `tests/backend_stability/regressions/test_p0_p1_history.py::test_paper_ingest_url_only_fetches_html_body` + `test_paper_ingest_url_non_html_does_not_crash` — 起内置 HTTP server 喂真实 HTML/PDF 响应，验证 status/title/annotation/abstract 全部落位。
**优先级**: ~~P0~~ ✅ 已修复

## 2026-04-17 outline_generate 忽视已选 contributions [FIXED 2026-05-07]
**场景**: ModalGate v3 论文撰写。Step 2 `writing_architecture` 拿到了我们 direction_proposal 的 4 条 contributions，产出 ModalGate 架构；Step 3 `outline_generate(project_id=4, template='kdd')` 却完全忽略了 contributions 与 writing_architecture 结果，凭 topic 10 的 evidence pack 自动编出一篇名为 "SAGE-Fuse" 的无关论文（不同方法、不同贡献）。
**现状**: `execution/llm_primitives.py::outline_generate` 其实已经有三级 fallback（arg → `topics.contributions` → `writing_architecture` artifact），并且在三个都空时会抛 `ValueError`。真正让这条路径长期静默失败的是一个次生 bug：`topic_set_contributions` 写 `topics.updated_at` 但 `topics` 表**从未有这一列**，每次调用直接 `OperationalError`，用户以为记下了 contributions，实际一行都没落库，fallback 1、2 都等于空。
**修复**: migration 065 给 `topics` 加了 `updated_at` 列并回填 `created_at`，让 `topic_set_contributions` 能真正持久化。fallback 路径未改（已经正确），但现在 upstream 存得下，outline_generate 才读得到。
**Regression**: `tests/backend_stability/regressions/test_p0_p1_history.py::test_outline_generate_reads_topic_contributions` — 用 `topic_set_contributions` 种入一句特征字符串，stub LLM client 捕获 prompt，断言字符串逐字出现在发给 LLM 的 prompt 里。`test_outline_generate_refuses_empty_contributions` 继续守护"没 contributions 时必须拒绝而非 hallucinate"这一边界。
**优先级**: ~~P1~~ ✅ 已修复

## 2026-05-07 papers.s2_id `DEFAULT '' UNIQUE` 多行空字符串相互冲突 [FIXED 2026-05-07]
**场景**: backend stability fixture loader 直接用 INSERT OR IGNORE 写入 5 个测试论文（distinct arxiv_id, distinct doi, 缺省 s2_id）。第二行起 `s2_id=''` 与第一行已存在的 `''` 触发 UNIQUE 冲突，OR IGNORE 静默丢弃，最终库里只剩 1 行。
**根因**: `migrations/001_initial_schema.sql` 中 `s2_id TEXT DEFAULT '' UNIQUE`（同样问题潜在存在于 `doi` / `arxiv_id`），在 SQLite 里空字符串被视为合法值参与 UNIQUE 比较——任意两条无 s2_id 的论文必然冲突。
**修复**: `migrations/064_paper_identifiers_nullable.sql` 重建 `papers` 表，把 `doi`/`arxiv_id`/`s2_id` 改为 nullable UNIQUE（NULL 不参与 UNIQUE 比较），并把现有 `''` 通过 `NULLIF(TRIM(…), '')` 回填为 NULL。
**Regression**: `tests/backend_stability/regressions/test_p0_p1_history.py::test_papers_identifier_columns_allow_multiple_nulls` — 插 3 行无 s2_id 的论文必须共存，但两行同一真实 s2_id 仍必须抛 IntegrityError。
**优先级**: ~~P0（数据正确性）~~ ✅ 已修复




## 2026-05-11 metadata-incomplete paper update/merge 工具缺口

**场景**: 多篇 URL-only / DOI-only / OpenReview-only 论文以 DOI、PDF URL 或 OpenReview URL 入库后 metadata incomplete。
**问题/发现**: 找到正式标题和来源后，当前可见 MCP 只有 `paper_ingest`，没有安全的 `paper_update_metadata` / `paper_merge_duplicate`；直接 SQL 写入又违反论文管理规范，导致只能新入库或在 artifact 中备注。
**建议改进**: 增加 `paper_update_metadata(paper_id, fields, source_evidence)` 与 `paper_merge_duplicates(canonical_id, duplicate_ids)`，并要求记录外部核对来源。
**优先级**: P1

## 2026-05-17 literature-search 多源检索遇到 429/timeout 时缺少快速降级

**场景**: 初始化某个大规模 literature-survey topic 后，用 `rh search papers --topic ... --year-from 2023 --log-run` 执行多源检索，准备为科研 agent 综述记录系统检索日志。

**问题/发现**:
- Semantic Scholar 免费接口连续返回 HTTP 429，arXiv API 多次 read timeout，单个 query 需要很久才能完成。
- CLI 当前会逐 provider 重试，适合完整采集，但不适合交互式 session 中的“先建立种子池/检索式”的快速推进。
- 执行到第 3 个 query 时需要人工 kill，最终只成功记录前 2 个 search_runs。

**建议改进**:
1. 增加 `--provider` / `--exclude-provider` 参数，允许交互式检索临时跳过 rate-limited provider。
2. 增加 `--timeout-seconds` / `--fast-fail` 参数，超时后保留已返回 provider 的结果并记录 partial status。
3. 在 search_runs 中记录 provider_errors，而不是只在 JSON 文件里保存，便于 provenance 追踪检索不完整的原因。
4. 为新 topic 初始化提供 `seed-search-fast` 模式：优先 OpenAlex/CrossRef/PASA + web-derived seeds，稍后后台补 S2/arXiv。

**优先级**: P1
