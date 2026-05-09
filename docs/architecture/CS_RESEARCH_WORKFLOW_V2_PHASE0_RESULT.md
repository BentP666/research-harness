# Phase 0 Result — CSO_MODE Decision

**Date**: 2026-04-23
**Status**: COMPLETE
**Decision**: `CSO_MODE = "llm_fallback"` (CSO reserved as coarse auxiliary signal)

## Validation summary

Ran `scripts/phase0/validate_cso.py` against 30 arxiv-fetched CS papers with `modules="syntactic"`, `fast_classification=True`, `delete_outliers=False` (cache path only, no 2GB word2vec).

```
hits=2/30 (6.7%) misses=28 generic=0
```

## Why the hit rate is low (and why it is NOT a bug)

CSO returns **coarse, correct** topics rather than the fine-grained labels our test vocabulary expected.

| Expected (fine) | CSO returned (coarse) | Verdict |
|---|---|---|
| `reward model`, `reinforcement learning` | `generative ai`, `natural language processing`, `deep learning` | coarse but **accurate category** |
| `instruction tuning`, `language model` | `natural language processing`, `generative ai` | coarse but **accurate category** |
| `algorithm`, `graph theory` | `graph theory`, `approximation algorithms` | **fine match** (hit) |

- **Zero generic labels** (no "computer science" / "machine learning" noise)
- **Zero wrong categories** (everything returned is on-topic)
- The miss is not *incorrect output* — it's *vocabulary-granularity mismatch*

## Implications

| Use case | Suitability |
|---|---|
| Domain spine / area labels (coarse bucketing) | ✅ CSO works, vocabulary stable |
| Red-ocean clustering (many papers → same coarse topic = signal) | ✅ Coarseness helps |
| Fine-grained task/method tagging | ❌ LLM required |
| Novel-terminology papers (2023+) | ❌ CSO vocabulary predates |

## Decision

**`CSO_MODE = "llm_fallback"`** for the primary CS classification path.

Additional guidance for downstream phases:

1. **Phase 2 task classification** uses LLM (not CSO batch)
2. **CSO may still be invoked as a supplementary signal** for coarse domain bucketing where its deterministic + zero-token cost is valuable — keep the plumbing, just don't make it authoritative
3. **Do not require the 2GB `model.v2.p`** in any user-facing install path. The syntactic cache (`token-to-cso-combined.json`, ~70 MB) is sufficient for the supplementary role
4. **Install experience**: `pip install research-harness[cs]` must not trigger the 2GB download. Gate behind explicit `rh cs install --full-model` command

## Follow-on recommendation for install UX

Per the separate user-experience discussion:
- Default: `pip install research-harness` works with LLM classification only (no large download)
- `[cs]` extra installs the cso-classifier package but only the 70 MB cache
- `rh cs install --full-model` is an explicit opt-in command that downloads the 2GB word2vec, with progress bar and size warning

The 1.7 GB truncated `model.p` from the initial attempt can be deleted; it is not used by `llm_fallback` mode.

## Artifacts

- `scripts/phase0/validation_papers.json` — 30 labeled test papers
- `scripts/phase0/validate_cso.py` — coverage validator (macOS-safe, bypasses word2vec)
- `scripts/phase0/cso_validation_report.json` — full per-paper results
- `scripts/cso_setup.py` — one-shot full-model downloader (reserve for opt-in path)

## Exit criteria (all green)

- [x] Python 3.11+ enforced in pyproject.toml (packages/{research_harness, paperindex, llm_router})
- [x] cso-classifier installed under `.venv-cs` (Python 3.12)
- [x] 30 validation papers fetched from arxiv
- [x] CSO coverage validated on cache path (6.7% strict / 100% coarse-correct)
- [x] `CSO_MODE` decision documented

## Next phase

Proceed to **Phase M** (paperindex internalization, agreed separately) → then **Phase 1** (CS retrieval + cs_harvest) with LLM path for classification.
