"""
TFRBench Forecasting Experiment — direct vs reasoning prompting
===============================================================

Loads TFRBench public data (historical_window has 14 steps, NO future ground
truth). To get evaluable metrics we self-supervise: first 10 steps as
"history", last 4 steps as "ground truth". Compare two prompting strategies.

Output: results/<timestamp>.jsonl + summary table printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

EXPERIMENT_DIR = Path(__file__).parent
DATA_DIR = EXPERIMENT_DIR / "data"
RESULTS_DIR = EXPERIMENT_DIR / "results"

# Add repo to sys.path so llm_router imports work
REPO_ROOT = EXPERIMENT_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "llm_router"))


def load_samples(path: Path, max_samples: int) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data[:max_samples]


def format_history(columns: list[str], rows: list[list[float]], index: list[str]) -> str:
    """Render the historical steps as a readable table."""
    header = " | ".join(columns)
    lines = [f"# time | {header}"]
    for ts, row in zip(index, rows):
        vals = " | ".join(
            f"{v:.4g}" if abs(v) < 1e6 else f"{v:.2e}" for v in row
        )
        lines.append(f"{ts} | {vals}")
    return "\n".join(lines)


DIRECT_PROMPT = """You are a time series forecasting expert.
Given the historical data below, predict the next {horizon} values.

Columns: {columns}

Historical window ({context_len} steps):
{history}

Output ONLY a JSON array of arrays, each inner array has {n_cols} floats
matching [{columns}], one per future step. Example:
[[v1,v2,v3,v4,v5], [v1,v2,v3,v4,v5], ...]
{horizon} rows total.
"""


REASONING_PROMPT = """You are a time series forecasting expert.
First analyze the historical data, then predict the next {horizon} values.

Columns: {columns}

Historical window ({context_len} steps):
{history}

Step 1: Analyze trend, seasonality, volatility, cross-channel relations.
Step 2: Based on the analysis, predict the next {horizon} steps.

Format:
REASONING: <your 3-5 sentence analysis>
PREDICTION: <JSON array of {horizon} rows, each with {n_cols} floats>
"""


def build_prompt(sample: dict, strategy: str, split_at: int) -> tuple[str, list[list[float]]]:
    """Returns (prompt, ground_truth_rows)."""
    hw = sample["historical_window"]
    rows = hw["data"]
    idx = hw["index"]
    cols = hw["columns"]

    history_rows = rows[:split_at]
    history_idx = idx[:split_at]
    gt_rows = rows[split_at:]

    history = format_history(cols, history_rows, history_idx)
    horizon = len(gt_rows)
    prompt_tpl = DIRECT_PROMPT if strategy == "direct" else REASONING_PROMPT
    prompt = prompt_tpl.format(
        columns=", ".join(cols),
        context_len=len(history_rows),
        history=history,
        n_cols=len(cols),
        horizon=horizon,
    )
    return prompt, gt_rows


def parse_prediction(text: str, strategy: str, horizon: int, n_cols: int) -> tuple[str, list[list[float]]]:
    """Extract REASONING + PREDICTION from model output."""
    reasoning = ""
    pred_text = text
    if strategy == "reasoning":
        m = re.search(r"PREDICTION\s*:\s*", text, re.IGNORECASE)
        if m:
            reasoning = text[: m.start()].replace("REASONING:", "").strip()
            pred_text = text[m.end():]
        else:
            reasoning = text.strip()

    # Find the first JSON array
    m = re.search(r"\[\s*\[[\s\S]*?\]\s*\]", pred_text)
    if not m:
        return reasoning, []
    try:
        arr = json.loads(m.group())
    except json.JSONDecodeError:
        return reasoning, []

    # Normalize
    out: list[list[float]] = []
    for row in arr[:horizon]:
        if isinstance(row, (int, float)):
            row = [float(row)]
        if not isinstance(row, list):
            continue
        try:
            out.append([float(v) for v in row[:n_cols]])
        except (TypeError, ValueError):
            continue
    return reasoning, out


def compute_errors(pred: list[list[float]], gt: list[list[float]]) -> dict[str, float]:
    """MAE, RMSE, per-channel MAPE. Requires same shape; pads with NaN if short."""
    import math
    if not pred or not gt:
        return {"mae": float("nan"), "rmse": float("nan"), "mape": float("nan"), "n_matched": 0}
    n = min(len(pred), len(gt))
    if n == 0:
        return {"mae": float("nan"), "rmse": float("nan"), "mape": float("nan"), "n_matched": 0}
    abs_errs: list[float] = []
    sq_errs: list[float] = []
    pct_errs: list[float] = []
    for i in range(n):
        p = pred[i]
        g = gt[i]
        w = min(len(p), len(g))
        for j in range(w):
            err = p[j] - g[j]
            abs_errs.append(abs(err))
            sq_errs.append(err * err)
            if abs(g[j]) > 1e-9:
                pct_errs.append(abs(err / g[j]))
    if not abs_errs:
        return {"mae": float("nan"), "rmse": float("nan"), "mape": float("nan"), "n_matched": 0}
    mae = sum(abs_errs) / len(abs_errs)
    rmse = math.sqrt(sum(sq_errs) / len(sq_errs))
    mape = (sum(pct_errs) / len(pct_errs)) if pct_errs else float("nan")
    return {"mae": mae, "rmse": rmse, "mape": mape, "n_matched": n}


def call_llm(prompt: str, provider: str, max_tokens: int = 4096) -> dict[str, Any]:
    """Dispatch through llm_router so plugin providers work."""
    from llm_router import resolve_llm_config, get_provider

    cfg = resolve_llm_config({"provider": provider})
    fn = get_provider(provider)
    t0 = time.time()
    try:
        text = fn(prompt, cfg.model, api_key=cfg.api_key, base_url=cfg.base_url, temperature=0.0)
        return {"text": text, "elapsed_s": time.time() - t0, "error": None}
    except Exception as e:
        return {"text": "", "elapsed_s": time.time() - t0, "error": str(e)[:300]}


def run(providers: list[str], datasets: list[str], max_samples: int, split_at: int,
        strategies: list[str], out_path: Path) -> list[dict]:
    results: list[dict] = []
    with open(out_path, "w") as out_fh:
        for provider in providers:
            print(f"\n{'='*70}")
            print(f"Provider: {provider}")
            print(f"{'='*70}")
            for ds_file in datasets:
                ds_path = DATA_DIR / ds_file
                if not ds_path.exists():
                    print(f"  SKIP {ds_file} (not found)")
                    continue
                samples = load_samples(ds_path, max_samples)
                print(f"  Dataset: {ds_file} ({len(samples)} samples)")

                for strategy in strategies:
                    t0 = time.time()
                    rows: list[dict] = []
                    for sample in samples:
                        prompt, gt = build_prompt(sample, strategy, split_at)
                        horizon = len(gt)
                        n_cols = len(sample["historical_window"]["columns"])
                        resp = call_llm(prompt, provider)
                        reasoning, pred = parse_prediction(
                            resp["text"], strategy, horizon, n_cols
                        )
                        errs = compute_errors(pred, gt)
                        rec = {
                            "provider": provider,
                            "dataset": sample["dataset"],
                            "sample_id": sample["id"],
                            "strategy": strategy,
                            "horizon": horizon,
                            "n_cols": n_cols,
                            "pred_rows": len(pred),
                            "reasoning_len": len(reasoning),
                            "error_msg": resp["error"],
                            "elapsed_s": resp["elapsed_s"],
                            **errs,
                        }
                        rows.append(rec)
                        out_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        out_fh.flush()
                        results.append(rec)

                    elapsed = time.time() - t0
                    ok = sum(1 for r in rows if r["pred_rows"] > 0 and not r["error_msg"])
                    mean_mae = _mean([r["mae"] for r in rows if r["mae"] == r["mae"]])
                    print(
                        f"    {strategy:10s}: {ok}/{len(rows)} ok, "
                        f"mean_mae={mean_mae:.4f}, {elapsed:.1f}s"
                    )
    return results


def _mean(xs: list[float]) -> float:
    xs = [x for x in xs if x == x]  # drop NaN
    return sum(xs) / len(xs) if xs else float("nan")


def summary_table(results: list[dict]) -> None:
    """Print aggregate comparison per (provider, strategy)."""
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'provider':14s} {'strategy':10s} {'n':4s} {'ok':4s} {'mae':>10s} {'rmse':>10s} {'mape':>8s}")
    print("-" * 70)

    by_group: dict[tuple[str, str], list[dict]] = {}
    for r in results:
        by_group.setdefault((r["provider"], r["strategy"]), []).append(r)

    for (prov, strat), rows in sorted(by_group.items()):
        ok = sum(1 for r in rows if r["pred_rows"] > 0 and not r["error_msg"])
        mae = _mean([r["mae"] for r in rows])
        rmse = _mean([r["rmse"] for r in rows])
        mape = _mean([r["mape"] for r in rows])
        print(
            f"{prov:14s} {strat:10s} {len(rows):4d} {ok:4d} "
            f"{mae:10.4f} {rmse:10.4f} {mape:8.2%}"
        )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--providers", nargs="+", default=["anthropic", "openai"])
    p.add_argument("--datasets", nargs="+", default=["amazon_public.json", "apple_public.json"])
    p.add_argument("--max-samples", type=int, default=5)
    p.add_argument("--split-at", type=int, default=10,
                   help="Use first N steps as history, rest as ground truth")
    p.add_argument("--strategies", nargs="+", default=["direct", "reasoning"])
    p.add_argument("--out", default=None)
    args = p.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"run_{ts}.jsonl"

    # Ensure llm_router plugins are loaded
    from llm_router.plugins import load_plugins
    load_plugins()

    print(f"Output: {out_path}")
    print(f"Providers: {args.providers}")
    print(f"Datasets: {args.datasets}")
    print(f"Samples per dataset: {args.max_samples}")
    print(f"Self-supervised split: first {args.split_at} steps as history")
    print(f"Strategies: {args.strategies}")

    results = run(
        providers=args.providers,
        datasets=args.datasets,
        max_samples=args.max_samples,
        split_at=args.split_at,
        strategies=args.strategies,
        out_path=out_path,
    )
    summary_table(results)
    print(f"\nSaved {len(results)} results to {out_path}")


if __name__ == "__main__":
    main()
