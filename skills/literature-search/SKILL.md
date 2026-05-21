---
name: literature-search
description: Run comprehensive literature search for Research Harness. Trigger on phrases like "literature-search", "/literature-search", "文献检索", "系统检索论文", "帮我搜相关论文", or equivalent requests to search, shortlist, and ingest relevant papers.
---

# Literature Search

Use this skill for broad paper discovery.

## Workflow

1. Read `~/code/research-harness/docs/agent-guide.md` if topic context is unclear.
2. Clarify or infer:
   - research topic
   - time range
   - venue or domain constraints
3. Use `paper_search` or `rhub`-compatible search flow.
4. Deduplicate and rank results by relevance.
5. Recommend which papers to ingest and ingest them when the user intent is clearly operational rather than exploratory.

## Output

- concise search query formulation
- top relevant papers
- ingestion decision or next-step recommendation

## Frontier Attention Evidence

When the search supports a paper, survey, or topic-validation task, include a
frontier-attention pass:

- latest top academic signals: recent top-venue papers, best/oral/spotlight
  papers, benchmarks, surveys, and workshop/tutorial activity
- industry signals: official lab/company blogs, technical reports, SDKs,
  standards, open-source frameworks, and product releases
- trend summary: why the topic is timely now, and which scope boundaries the
  evidence does or does not support

Papers must be ingested under the topic; non-paper sources should be recorded
in a `frontier_attention_evidence` artifact with URL, date, source type, and
the claim they support.
