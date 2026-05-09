# Venue Family Mapping

Used by `venue_style_kit` 3-tier degradation (iter-08).

## Families

| Family | Members |
|--------|---------|
| NLP | EMNLP, ACL, NAACL, EACL, COLING, Findings |
| ML | NeurIPS, ICML, ICLR, AAAI, IJCAI, AISTATS |
| CV | CVPR, ICCV, ECCV |
| IR | SIGIR, WSDM, CIKM, KDD |
| Time Series | NeurIPS, ICML, ICLR, AAAI, KDD, IEEE, IJF |

## 3-Tier Degradation

1. **Exact match** (decided_venue appears in paper.venue) — use if >= 3 papers
2. **Family expansion** — expand to all family members, `source_venues` field records which venues were actually used
3. **Insufficient** — return 409 Conflict: "Need at least 3 reference papers for venue style analysis"

## Red Line (per Q4 review)

- Style kit MUST use real paper samples from the pool
- LLM-based style inference from non-matching papers is PROHIBITED
- `source_venues` field is mandatory and must accurately reflect which venues the papers came from
