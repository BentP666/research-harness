"""Demo mode — canned LLM response replay for onboarding without API keys."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CORPUS_PATH = Path(__file__).parent / "canned_auto_bidding.json"

_corpus: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _corpus
    if _corpus is None:
        if CORPUS_PATH.exists():
            _corpus = json.loads(CORPUS_PATH.read_text())
        else:
            _corpus = {}
    return _corpus


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def lookup(stage: str, primitive: str, prompt: str) -> dict | None:
    corpus = _load()
    key = f"{stage}:{primitive}:{prompt_hash(prompt)}"
    return corpus.get(key)


def list_entries() -> list[dict]:
    corpus = _load()
    return [
        {"key": k, "stage": v.get("stage"), "primitive": v.get("primitive")}
        for k, v in corpus.items()
    ]
