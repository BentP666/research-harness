# TFRBench E2E Test Plan — Research Harness Frontend

## Goal
Use a real research task (TFRBench: time series forecasting reasoning) to end-to-end test the Atlas frontend, covering the full research lifecycle.

## Research Task Summary
- **Paper**: TFRBench (Google, Apr 2026) — first benchmark evaluating *reasoning quality* of forecasting systems
- **Core question**: Does generating reasoning traces before predicting improve time series forecast accuracy?
- **Key finding**: ~40.2% → 56.6% accuracy with reasoning chains
- **Datasets**: 10 open datasets, 5 domains (Energy, Sales, Web/CloudOps, Transport, Finance)
- **Metrics**: MASE + LLM-as-Judge reasoning score
- **No GPU needed**: pure LLM API calls

## Test Journeys

### Journey 1: Topic Creation & Setup
1. Navigate to 研究中心 (`/research`)
2. Create new topic: "LLM时序预测推理能力评估 (TFRBench)"
3. Verify topic appears in sidebar/list
4. Check topic overview page loads correctly

### Journey 2: Paper Ingestion
1. Navigate to topic page
2. Ingest TFRBench paper (arXiv:2604.05364)
3. Verify paper appears in 文献资料 (`/library`)
4. Check paper metadata (title, authors, abstract)
5. Ingest 2-3 related papers:
   - TemporalBench (arXiv:2602.13272)
   - TimeSeriesExamAgent (arXiv:2604.10291)

### Journey 3: Literature Review
1. Navigate to 学术发现 (`/discover`)
2. Check if recommendations/trends work
3. Go to topic page, verify "Next Actions" card suggests literature review
4. Check stage pipeline progression

### Journey 4: Experiment Design
1. From topic page, check experiment design flow
2. Verify experiment variables are capturable:
   - Models: Claude Sonnet, GPT-4.1-mini, Gemini-2.5-Flash
   - Strategies: direct vs reasoning-chain
   - Datasets: 10 TFRBench datasets
   - Metrics: MASE, MAE, RMSE + LLM-Judge

### Journey 5: Reports
1. Navigate to 研究汇报 (`/reports`)
2. Check report template availability
3. Verify stage-gated templates (based on topic stage)

### Journey 6: Cross-cutting
1. **i18n**: Toggle language EN↔CN, verify all pages render correctly
2. **Top bar**: Check model status chip, token budget, settings
3. **Navigation**: All sidebar links work, mobile nav works
4. **Dark mode**: Toggle and verify
5. **Settings**: `/settings` page loads, scoring config at `/settings/scoring`
6. **Agents/Models**: `/agents` page shows model configurations

## Datasets Prepared
Located at `experiments/tfrbench/data/`:
- 10 JSON files, ~44MB total
- Format: `{id, dataset, historical_window: {index, columns, data}, future_window_timestamps}`

## Experiment Code Prepared
- `experiments/tfrbench/run_experiment.py` — async runner, supports Anthropic/OpenAI/Google
- `experiments/tfrbench/config.yaml` — experiment configuration
- Evaluation code (MASE + LLM-Judge) — pending

## Success Criteria
- [ ] All 6 journeys complete without errors
- [ ] Topic lifecycle visible in UI (create → ingest → review → experiment → report)
- [ ] No console errors on any page
- [ ] i18n works for both languages
- [ ] Mobile nav accessible
