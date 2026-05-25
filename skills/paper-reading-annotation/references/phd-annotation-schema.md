# PhD PDF Annotation Schema

Use this schema to create annotation plans for `scripts/phd_pdf_annotator.py`.

## JSON shape

```json
{
  "paper_id": 123,
  "title": "Paper title",
  "profile": "phd-quick-grasp-v1",
  "annotations": [
    {
      "anchor": "exact text fragment from the PDF",
      "page": 1,
      "category": "core-claim",
      "subject": "核心主张",
      "comment": "【核心主张】这里是作者真正希望读者相信的句子；后面需要检查实验/论证是否支撑。",
      "priority": 5
    }
  ]
}
```

`page` is optional and 1-based; include it whenever possible to reduce false matches.

## Required categories

For a full paper, cover at least these categories:

1. `problem` — What problem is defined?
2. `motivation` — Why does the problem matter?
3. `core-claim` — What does the paper want the reader to believe?
4. `theoretical-innovation` — New concept, taxonomy, abstraction, mechanism, formalization, or evaluation lens.
5. `application-innovation` — New task setting, domain transfer, system usage, deployment path, or practice implication.
6. `concept-boundary` — Definitions and distinctions that shape the paper's scope.
7. `method-taxonomy` — Method, framework, taxonomy, pipeline, or algorithmic skeleton.
8. `hidden-assumption` — Condition the method/taxonomy depends on but may not foreground.
9. `evidence` — Dataset, benchmark, case study, human evaluation, or survey protocol strength.
10. `baseline` — Baseline/comparison coverage or missing comparison.
11. `limitation-risk` — Explicit or implicit limitations, threats, safety/ethics/reproducibility issues.
12. `writing-move` — Notable writing structure, framing, figure/table design, or argument sequencing.
13. `surprise` — A surprising insight, framing choice, or unexpected implication.
14. `reusable-framing` — Sentence/structure useful for introduction, related work, or survey writing.
15. `rh-mapping` — How this maps to the current RH topic, workflow, artifact, gate, or evaluation design.
16. `follow-up` — Question or next citation-tracing/search action.

## Comment style

Use short Chinese comments with an explicit label:

- `【理论创新】...`
- `【应用创新】...`
- `【写作思路】...`
- `【惊喜点】...`
- `【证据检查】...`
- `【RH映射】...`

Bad comment: `Important.`

Good comment: `【理论创新】这不是实验贡献，而是把 agent 系统拆成可编码的四个维度；可直接改造成综述 taxonomy。`

## Density guidance

- Abstract/title: 2–4 annotations.
- Introduction: 6–10 annotations.
- Method/taxonomy: 8–14 annotations.
- Experiments/evidence/resources: 4–8 annotations.
- Limitations/challenges/conclusion: 4–8 annotations.
- Avoid highlighting whole pages; anchor exact sentences or short paragraphs.
