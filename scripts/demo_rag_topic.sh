#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Atlas Demo: RAG (Retrieval-Augmented Generation) Research Topic
# ─────────────────────────────────────────────────────────────────────────────
#
# Walks through the full research workflow:
#   1. Create domain & topic
#   2. Ingest landmark RAG papers from arXiv
#   3. Enrich metadata & download PDFs
#   4. Run analysis primitives (claims, gaps, reading prioritization)
#   5. Generate outline & draft sections
#   6. Initialize orchestrator for stage-gated progression
#
# Requirements:
#   - Python env with research_harness installed
#   - At least one LLM provider configured (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
#     OR run with --no-llm to skip LLM-dependent steps
#   - Internet access (arXiv / Semantic Scholar API)
#
# Usage:
#   ./scripts/demo_rag_topic.sh              # full demo with LLM steps
#   ./scripts/demo_rag_topic.sh --no-llm     # ingest-only, skip LLM primitives
#   ./scripts/demo_rag_topic.sh --dry-run    # print commands without executing
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

RH="python -m research_harness.cli"
NO_LLM=false
DRY_RUN=false
TOPIC_NAME="RAG-Survey-2024"
DOMAIN_NAME="NLP & Information Retrieval"

for arg in "$@"; do
  case "$arg" in
    --no-llm)  NO_LLM=true ;;
    --dry-run) DRY_RUN=true ;;
  esac
done

# ── helpers ──────────────────────────────────────────────────────────────────

step=0
run() {
  step=$((step + 1))
  echo ""
  echo "━━━ Step $step: $1"
  shift
  if $DRY_RUN; then
    echo "  [dry-run] $*"
  else
    eval "$@"
  fi
}

info() { echo "  ℹ  $*"; }
warn() { echo "  ⚠  $*"; }

# ── pre-flight ───────────────────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Atlas Demo — RAG Research Topic Walkthrough            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

if ! $DRY_RUN; then
  $RH doctor 2>/dev/null || warn "doctor check unavailable, continuing anyway"
fi

# ── 1. Domain & Topic ───────────────────────────────────────────────────────

run "Create research domain" \
  "$RH domain init '$DOMAIN_NAME' --description 'Natural language processing, retrieval systems, and information extraction'" \
  "|| info 'Domain may already exist, continuing'"

run "Create topic: $TOPIC_NAME" \
  "$RH topic init '$TOPIC_NAME' \
    --description 'Survey of Retrieval-Augmented Generation: architectures, chunking strategies, re-ranking, evaluation, and open problems' \
    --domain '$DOMAIN_NAME'" \
  "|| info 'Topic may already exist, continuing'"

# Capture topic ID for later steps
if ! $DRY_RUN; then
  TOPIC_ID=$($RH --json topic list 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
topics = data if isinstance(data, list) else data.get('topics', [])
for t in topics:
    if t.get('name') == '$TOPIC_NAME':
        print(t['id']); break
" 2>/dev/null || echo "")
  if [ -z "$TOPIC_ID" ]; then
    warn "Could not determine topic ID, using name-based commands"
    TOPIC_REF="$TOPIC_NAME"
  else
    TOPIC_REF="$TOPIC_ID"
    info "Topic ID: $TOPIC_ID"
  fi
else
  TOPIC_REF="<TOPIC_ID>"
fi

# ── 2. Ingest landmark RAG papers ──────────────────────────────────────────

PAPERS=(
  # The original RAG paper (Lewis et al., 2020)
  "2005.11401"
  # Self-RAG: Learning to Retrieve, Generate, and Critique (Asai et al., 2023)
  "2310.11511"
  # REPLUG: Retrieval-Augmented Black-Box Language Models (Shi et al., 2023)
  "2301.12652"
  # Active RAG (Jiang et al., 2023)
  "2305.06983"
  # Benchmarking Large Language Models in RAG (Chen et al., 2023)
  "2309.01431"
  # RAGAS: Automated Evaluation of RAG (Es et al., 2023)
  "2309.15217"
  # Lost in the Middle: How Language Models Use Long Contexts (Liu et al., 2023)
  "2307.03172"
  # Corrective RAG (Yan et al., 2024)
  "2401.15884"
  # RAG for LLMs: A Survey (Gao et al., 2024)
  "2312.10997"
  # REALM: Retrieval-Augmented Language Model Pre-Training (Guu et al., 2020)
  "2002.08909"
  # FiD: Leveraging Passage Retrieval with Generative Models (Izacard & Grave, 2020)
  "2007.01282"
  # Atlas: Few-shot Learning with Retrieval Augmented Language Models (Izacard et al., 2022)
  "2208.03299"
  # Adaptive-RAG (Jeong et al., 2024)
  "2403.14403"
  # Query Rewriting for RAG (Ma et al., 2023)
  "2305.14283"
  # Dense Passage Retrieval (Karpukhin et al., 2020)
  "2004.04906"
)

info "Ingesting ${#PAPERS[@]} landmark RAG papers from arXiv..."

for arxiv_id in "${PAPERS[@]}"; do
  run "Ingest arXiv:$arxiv_id" \
    "$RH paper ingest --arxiv-id '$arxiv_id' --topic '$TOPIC_NAME' --relevance high" \
    "|| info 'Paper $arxiv_id may already exist'"
done

# ── 3. Enrich metadata & download PDFs ─────────────────────────────────────

run "Enrich paper metadata from Semantic Scholar" \
  "$RH paper enrich --topic '$TOPIC_NAME'" \
  "|| info 'Enrichment done (some papers may lack S2 data)'"

run "Download PDFs and build annotations" \
  "$RH paper acquire --topic '$TOPIC_REF'" \
  "|| info 'Some PDFs may fail to download — that is OK for the demo'"

# ── 4. Topic overview ──────────────────────────────────────────────────────

run "Show topic overview" \
  "$RH topic overview '$TOPIC_NAME'"

run "Show venue & year distribution" \
  "$RH topic stats '$TOPIC_NAME'"

# ── 5. Analysis primitives (require LLM) ───────────────────────────────────

if $NO_LLM; then
  echo ""
  echo "━━━ Skipping LLM steps (--no-llm) ━━━"
  echo "  To run the full demo, configure an LLM provider and re-run without --no-llm."
  echo ""
else
  run "Prioritize reading order" \
    "$RH primitive exec reading_prioritize --topic $TOPIC_REF"

  run "Extract claims from papers" \
    "$RH primitive exec claim_extract --topic $TOPIC_REF" \
    "|| info 'Claim extraction may be partial if PDFs are missing'"

  run "Detect research gaps" \
    "$RH primitive exec gap_detect --topic $TOPIC_REF"

  run "Identify baselines for comparison" \
    "$RH primitive exec baseline_identify --topic $TOPIC_REF"

  # ── 6. Writing primitives ────────────────────────────────────────────────

  run "Set topic contributions" \
    "$RH topic set-contributions '$TOPIC_NAME' --text 'This survey provides: (1) a unified taxonomy of RAG architectures from naive retrieve-then-read to iterative and adaptive designs, (2) a systematic comparison of chunking, embedding, and re-ranking strategies, (3) analysis of evaluation frameworks including RAGAS and RGB benchmarks, and (4) identification of open problems in multi-hop reasoning, attribution, and real-time knowledge updates.'"

  run "Generate paper outline" \
    "$RH primitive exec outline_generate --topic $TOPIC_REF"

  run "Draft Introduction section" \
    "$RH primitive exec section_draft --topic $TOPIC_REF --args '{\"section\": \"introduction\"}'"

  run "Draft Related Work section" \
    "$RH primitive exec section_draft --topic $TOPIC_REF --args '{\"section\": \"related_work\"}'"
fi

# ── 7. Initialize orchestrator ─────────────────────────────────────────────

run "Initialize orchestrator (demo mode)" \
  "$RH orchestrator init --topic '$TOPIC_NAME' --mode demo" \
  "|| info 'Orchestrator may already be initialized'"

run "Show orchestrator status" \
  "$RH orchestrator status --topic '$TOPIC_NAME'"

# ── 8. Generate trends ────────────────────────────────────────────────────

run "Refresh domain trends from paper corpus" \
  "$RH trends refresh" \
  "|| info 'Trends refresh may need more papers across domains'"

# ── Done ───────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Demo complete!                                         ║"
echo "║                                                         ║"
echo "║  Next steps:                                            ║"
echo "║  • Open http://localhost:3000 to see the Atlas UI       ║"
echo "║  • Browse your papers at /library                       ║"
echo "║  • Check research trends at /discover                   ║"
echo "║  • Manage your topic at /topics/<id>                    ║"
echo "║                                                         ║"
echo "║  Continue from the CLI:                                 ║"
echo "║  rh paper list --topic '$TOPIC_NAME'                    ║"
echo "║  rh orchestrator advance --topic '$TOPIC_NAME'          ║"
echo "║  rh primitive exec section_draft --topic <ID> \\        ║"
echo "║      --args '{\"section\": \"method\"}'                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
