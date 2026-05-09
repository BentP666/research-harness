"""ROC / Youden's J threshold selection.

Given positive (accept) and negative (reject) scores, pick the threshold that
maximizes ``TPR - FPR``. Ties are broken toward the **higher** threshold so
that we are slightly conservative (harder to pass).
"""

from __future__ import annotations


def youdens_j_threshold(
    positives: list[float],
    negatives: list[float],
    default: float,
) -> tuple[float, float, float]:
    """Return (threshold, false_rollback_rate, reject_rate).

    - ``false_rollback_rate`` = fraction of positives (accept-labeled) that
      score *below* the threshold (would be wrongly rolled back).
    - ``reject_rate`` = fraction of negatives (reject-labeled) correctly scoring
      below the threshold (rejection recall).
    - If either class is empty, return the provided ``default`` with NaN-like
      0.0 rates.
    """
    if not positives or not negatives:
        return (float(default), 0.0, 0.0)

    candidates = sorted(set(positives) | set(negatives))

    best_t = float(default)
    best_j = float("-inf")
    for t in candidates:
        tpr = sum(1 for p in positives if p >= t) / len(positives)
        fpr = sum(1 for n in negatives if n >= t) / len(negatives)
        j = tpr - fpr
        # Tie-break: prefer higher threshold (more conservative gate).
        if j > best_j or (j == best_j and t > best_t):
            best_j = j
            best_t = t

    false_rollback = sum(1 for p in positives if p < best_t) / len(positives)
    reject_rate = sum(1 for n in negatives if n < best_t) / len(negatives)
    return (round(best_t, 2), round(false_rollback, 3), round(reject_rate, 3))
