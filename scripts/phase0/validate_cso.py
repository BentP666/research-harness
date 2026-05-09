"""Run CSO over 30 validation papers; compute hit rate.

On macOS, CSOClassifier.batch_run() uses multiprocessing (spawn), so the
entire script must live behind `if __name__ == '__main__':` — otherwise
worker processes re-import this module and crash with RuntimeError.
"""
import json
from pathlib import Path
from cso_classifier.classifier import CSOClassifier


def main() -> None:
    papers = json.loads(Path("scripts/phase0/validation_papers.json").read_text())
    batch_input = {
        p["id"]: {
            "title": p["title"],
            "abstract": p["abstract"],
            "keywords": " ".join(p["keywords"]),
        }
        for p in papers
    }
    cc = CSOClassifier(
        modules="syntactic",
        enhancement="first",
        explanation=False,
        get_weights=False,
        fast_classification=True,
        delete_outliers=False,  # CRITICAL: keeps use_full_model=False, skips 2GB model.p
    )
    results = cc.batch_run(batch_input)

    hits, misses, generic = 0, 0, 0
    GENERIC_TERMS = {
        "computer science",
        "artificial intelligence",
        "machine learning",
        "deep learning",
    }
    report = []
    for p in papers:
        got = set(results[p["id"]].get("enhanced", []))
        expected = {c.lower() for c in p["expected_concepts"]}
        overlap = {g.lower() for g in got} & expected
        if overlap:
            hits += 1
            status = "hit"
        elif got <= {t.lower() for t in GENERIC_TERMS}:
            generic += 1
            status = "too_generic"
        else:
            misses += 1
            status = "miss"
        report.append(
            {
                "id": p["id"],
                "category": p["category"],
                "expected": list(expected),
                "got": list(got)[:10],
                "status": status,
            }
        )

    total = len(papers)
    Path("scripts/phase0/cso_validation_report.json").write_text(
        json.dumps(
            {
                "hits": hits,
                "misses": misses,
                "generic": generic,
                "total": total,
                "hit_rate": hits / total,
                "details": report,
            },
            indent=2,
        )
    )
    print(f"hits={hits}/{total} ({hits/total:.1%}) misses={misses} generic={generic}")


if __name__ == "__main__":
    main()
