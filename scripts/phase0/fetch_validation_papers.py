"""Auto-source 30 validation papers for Phase 0 CSO coverage test.

Categories: 10 LLM alignment, 10 diffusion/multimodal, 5 agents, 5 classical CS.
Uses arxiv API directly (no RH dependency needed).
"""
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
from pathlib import Path

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}

QUERIES = [
    # (category_query, expected_concepts, count, category_label)
    ("cat:cs.LG AND (all:RLHF OR all:\"reinforcement learning from human feedback\")",
     ["reinforcement learning", "reward model"], 3, "llm_alignment"),
    ("cat:cs.CL AND all:\"instruction tuning\"",
     ["instruction tuning", "language model"], 3, "llm_alignment"),
    ("cat:cs.CL AND (all:\"alignment\" AND all:\"language model\")",
     ["language model", "alignment"], 4, "llm_alignment"),

    ("cat:cs.CV AND all:\"diffusion model\"",
     ["diffusion model", "image generation"], 4, "diffusion_multimodal"),
    ("cat:cs.CV AND all:\"multimodal\" AND all:\"vision language\"",
     ["multimodal learning", "vision-language model"], 3, "diffusion_multimodal"),
    ("cat:cs.CV AND all:\"text-to-image\"",
     ["text-to-image", "image generation"], 3, "diffusion_multimodal"),

    ("cat:cs.AI AND all:\"autonomous agent\"",
     ["autonomous agent", "planning"], 3, "agents"),
    ("cat:cs.AI AND all:\"tool use\" AND all:\"language model\"",
     ["tool use", "language model"], 2, "agents"),

    ("cat:cs.DS AND all:\"graph algorithm\"",
     ["graph theory", "algorithm"], 3, "classical"),
    ("cat:cs.PL AND all:\"type system\"",
     ["type system", "programming language"], 2, "classical"),
]


def fetch_arxiv(query: str, max_results: int = 5) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    })
    url = f"{ARXIV_API}?{params}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        xml = resp.read()
    root = ET.fromstring(xml)
    papers = []
    for entry in root.findall("atom:entry", NS):
        title = entry.find("atom:title", NS).text.strip().replace("\n", " ")
        abstract = entry.find("atom:summary", NS).text.strip().replace("\n", " ")
        arxiv_id = entry.find("atom:id", NS).text.strip().split("/abs/")[-1]
        categories = [c.attrib["term"] for c in entry.findall("atom:category", NS)]
        papers.append({
            "title": title,
            "abstract": abstract[:800],
            "arxiv_id": arxiv_id,
            "categories": categories,
        })
    return papers


def main():
    all_papers = []
    idx = 0
    for query, expected, count, cat in QUERIES:
        print(f"Fetching {cat}: {query[:60]}...")
        try:
            results = fetch_arxiv(query, max_results=count + 2)
        except Exception as e:
            print(f"  WARN: {e}")
            results = []
        for p in results[:count]:
            idx += 1
            all_papers.append({
                "id": f"{cat}_{idx}",
                "category": cat,
                "title": p["title"],
                "abstract": p["abstract"],
                "keywords": p["categories"][:5],
                "expected_concepts": expected,
                "arxiv_id": p["arxiv_id"],
            })
        time.sleep(3)  # arxiv rate limit

    print(f"\nCollected {len(all_papers)} papers")
    out = Path("scripts/phase0/validation_papers.json")
    out.write_text(json.dumps(all_papers, indent=2, ensure_ascii=False))
    print(f"Written to {out}")

    # Summary
    from collections import Counter
    cats = Counter(p["category"] for p in all_papers)
    for c, n in sorted(cats.items()):
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()
