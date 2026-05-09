"""
TFRBench Experiment Runner
Compare direct LLM prediction vs reasoning-chain prediction on time series forecasting.
"""

import json
import os
import time
import asyncio
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

import yaml

EXPERIMENT_DIR = Path(__file__).parent
DATA_DIR = EXPERIMENT_DIR / "data"
RESULTS_DIR = EXPERIMENT_DIR / "results"


@dataclass
class Sample:
    id: str
    dataset: str
    columns: list[str]
    historical_data: list[list[float]]
    historical_index: list[str]
    future_timestamps: list[str]
    n_channels: int = field(init=False)
    horizon: int = field(init=False)
    context_len: int = field(init=False)

    def __post_init__(self):
        self.n_channels = len(self.columns)
        self.horizon = len(self.future_timestamps)
        self.context_len = len(self.historical_data)


def load_dataset(path: Path, max_samples: int | None = None) -> list[Sample]:
    with open(path) as f:
        raw = json.load(f)
    if max_samples:
        raw = raw[:max_samples]
    samples = []
    for r in raw:
        hw = r["historical_window"]
        samples.append(Sample(
            id=r["id"],
            dataset=r["dataset"],
            columns=hw["columns"],
            historical_data=hw["data"],
            historical_index=hw["index"],
            future_timestamps=r["future_window_timestamps"],
        ))
    return samples


def format_ts_for_prompt(sample: Sample) -> str:
    lines = []
    lines.append(f"Dataset: {sample.dataset}")
    lines.append(f"Columns: {', '.join(sample.columns)}")
    lines.append(f"Historical window ({sample.context_len} steps):")
    for i, (ts, row) in enumerate(zip(sample.historical_index, sample.historical_data)):
        vals = ", ".join(f"{v:.4f}" if abs(v) < 1e6 else f"{v:.0f}" for v in row)
        lines.append(f"  {ts}: [{vals}]")
    lines.append(f"\nForecast horizon: {sample.horizon} steps")
    lines.append(f"Future timestamps: {', '.join(sample.future_timestamps[:5])}{'...' if sample.horizon > 5 else ''}")
    return "\n".join(lines)


DIRECT_PROMPT = """You are a time series forecasting expert. Given the historical data below, predict the future values.

{ts_data}

Return your prediction as a JSON array of arrays, where each inner array has {n_channels} values corresponding to [{columns}].
Return ONLY the JSON array, no other text. Example format:
[[v1_t1, v2_t1], [v1_t2, v2_t2], ...]

Prediction ({horizon} steps):"""


REASONING_PROMPT = """You are a time series forecasting expert. Given the historical data below, first analyze the patterns, then predict.

{ts_data}

Step 1: Analyze the time series. Consider:
- Trend direction and strength
- Seasonality or periodic patterns
- Recent changes or anomalies
- Cross-channel dependencies (if multivariate)
- Any domain-specific patterns

Step 2: Based on your analysis, predict the next {horizon} steps.

Format your response as:
REASONING: <your analysis>
PREDICTION: <JSON array of arrays with {n_channels} values per step, e.g. [[v1, v2], [v1, v2], ...]>"""


def build_prompt(sample: Sample, strategy: str) -> str:
    ts_data = format_ts_for_prompt(sample)
    columns = ", ".join(sample.columns)
    if strategy == "direct":
        return DIRECT_PROMPT.format(
            ts_data=ts_data, n_channels=sample.n_channels,
            columns=columns, horizon=sample.horizon,
        )
    elif strategy == "reasoning":
        return REASONING_PROMPT.format(
            ts_data=ts_data, n_channels=sample.n_channels,
            columns=columns, horizon=sample.horizon,
        )
    raise ValueError(f"Unknown strategy: {strategy}")


async def call_anthropic(prompt: str, model: str) -> dict[str, Any]:
    import anthropic
    client = anthropic.AsyncAnthropic()
    t0 = time.time()
    resp = await client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - t0
    text = resp.content[0].text
    return {
        "text": text,
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "elapsed_s": elapsed,
    }


async def call_openai(prompt: str, model: str) -> dict[str, Any]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    t0 = time.time()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )
    elapsed = time.time() - t0
    choice = resp.choices[0]
    return {
        "text": choice.message.content,
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
        "elapsed_s": elapsed,
    }


async def call_google(prompt: str, model: str) -> dict[str, Any]:
    import google.generativeai as genai
    t0 = time.time()
    gm = genai.GenerativeModel(model)
    resp = await asyncio.to_thread(gm.generate_content, prompt)
    elapsed = time.time() - t0
    return {
        "text": resp.text,
        "input_tokens": getattr(resp.usage_metadata, "prompt_token_count", 0),
        "output_tokens": getattr(resp.usage_metadata, "candidates_token_count", 0),
        "elapsed_s": elapsed,
    }


PROVIDERS = {
    "anthropic": call_anthropic,
    "openai": call_openai,
    "google": call_google,
}


def parse_prediction(text: str, strategy: str, n_channels: int, horizon: int) -> tuple[str, list[list[float]]]:
    reasoning = ""
    pred_text = text

    if strategy == "reasoning":
        if "PREDICTION:" in text:
            parts = text.split("PREDICTION:", 1)
            reasoning = parts[0].replace("REASONING:", "").strip()
            pred_text = parts[1].strip()
        elif "REASONING:" in text:
            reasoning = text.split("REASONING:", 1)[1].strip()
            pred_text = text

    # Extract JSON array from text
    import re
    match = re.search(r'\[[\s\S]*\]', pred_text)
    if not match:
        return reasoning, []

    try:
        arr = json.loads(match.group())
        if arr and not isinstance(arr[0], list):
            arr = [[v] for v in arr]
        arr = arr[:horizon]
        return reasoning, arr
    except json.JSONDecodeError:
        return reasoning, []


async def run_sample(
    sample: Sample,
    strategy: str,
    provider: str,
    model_id: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    prompt = build_prompt(sample, strategy)
    async with semaphore:
        try:
            call_fn = PROVIDERS[provider]
            result = await call_fn(prompt, model_id)
        except Exception as e:
            return {
                "id": sample.id, "dataset": sample.dataset,
                "strategy": strategy, "error": str(e),
                "reasoning": "", "prediction": [],
            }

    reasoning, prediction = parse_prediction(
        result["text"], strategy, sample.n_channels, sample.horizon,
    )
    return {
        "id": sample.id,
        "dataset": sample.dataset,
        "strategy": strategy,
        "reasoning": reasoning,
        "prediction": prediction,
        "raw_response": result["text"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "elapsed_s": result["elapsed_s"],
    }


async def run_experiment(config: dict) -> list[dict]:
    max_samples = config["data"].get("max_samples_per_dataset")
    dataset_group = config.get("dataset_group", "quick")
    dataset_files = config["datasets"][dataset_group]
    strategies = [s["name"] for s in config["strategies"]]
    models = config["models"]
    concurrency = config.get("concurrency", 5)
    semaphore = asyncio.Semaphore(concurrency)

    all_results = []

    for model_cfg in models:
        model_name = model_cfg["name"]
        provider = model_cfg["provider"]
        model_id = model_cfg["model_id"]
        print(f"\n{'='*60}")
        print(f"Model: {model_name} ({model_id})")
        print(f"{'='*60}")

        for ds_file in dataset_files:
            ds_path = DATA_DIR / ds_file
            if not ds_path.exists():
                print(f"  SKIP {ds_file} (not found)")
                continue

            samples = load_dataset(ds_path, max_samples)
            ds_name = ds_file.replace("_public.json", "")
            print(f"\n  Dataset: {ds_name} ({len(samples)} samples)")

            for strategy in strategies:
                print(f"    Strategy: {strategy} ... ", end="", flush=True)
                t0 = time.time()

                tasks = [
                    run_sample(sample, strategy, provider, model_id, semaphore)
                    for sample in samples
                ]
                results = await asyncio.gather(*tasks)

                elapsed = time.time() - t0
                errors = sum(1 for r in results if r.get("error"))
                empty = sum(1 for r in results if not r.get("prediction") and not r.get("error"))
                ok = len(results) - errors - empty
                total_tokens = sum(r.get("input_tokens", 0) + r.get("output_tokens", 0) for r in results)

                print(f"{ok} ok, {empty} empty, {errors} err | {elapsed:.1f}s | {total_tokens} tokens")

                for r in results:
                    r["model"] = model_name
                    r["model_id"] = model_id
                all_results.extend(results)

    return all_results


def main():
    parser = argparse.ArgumentParser(description="TFRBench experiment runner")
    parser.add_argument("--config", default=str(EXPERIMENT_DIR / "config.yaml"))
    parser.add_argument("--dataset-group", default="quick", choices=["quick", "all"])
    parser.add_argument("--models", nargs="*", help="Filter to specific model names")
    parser.add_argument("--strategies", nargs="*", help="Filter to specific strategies")
    parser.add_argument("--max-samples", type=int, help="Override max samples per dataset")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    config["dataset_group"] = args.dataset_group
    config["concurrency"] = args.concurrency

    if args.max_samples is not None:
        config["data"]["max_samples_per_dataset"] = args.max_samples
    if args.models:
        config["models"] = [m for m in config["models"] if m["name"] in args.models]
    if args.strategies:
        config["strategies"] = [s for s in config["strategies"] if s["name"] in args.strategies]

    results = asyncio.run(run_experiment(config))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.output) if args.output else RESULTS_DIR / f"run_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path} ({len(results)} entries)")


if __name__ == "__main__":
    main()
