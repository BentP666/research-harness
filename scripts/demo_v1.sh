#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Research Harness v0.3.0 Demo
# ─────────────────────────────────────────────────────────────────────────────
#
# End-to-end walk-through of the v0.3.0 pipeline:
#
#   1. Create a research topic (default: LLM Agents for Time-Series Reasoning)
#   2. Seed it with 15 arXiv papers via `paper_search` + `paper_ingest`
#   3. Kick off a multi-round expansion job (100 retrieval / 20 deep-read /
#      3 rounds) that fans deep-read across every available LLM provider
#   4. Wait for the expansion to finish, printing per-paper provider logs
#   5. Emit a topic overview report to stdout
#
# Requirements:
#   - Backend running at http://localhost:8000 (python -m research_harness_mcp.http_api)
#   - At least one LLM provider configured — any of:
#       OPENAI_API_KEY, ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN,
#       KIMI_API_KEY, or CURSOR_AGENT CLI on PATH.
#
# Usage:
#   ./scripts/demo_v1.sh                    # standard demo
#   ./scripts/demo_v1.sh --quick            # fast smoke test (5 papers, 1 round)
#   ./scripts/demo_v1.sh --topic "Your topic name"
#
# The script is idempotent: re-running resumes where the last run left off.
# ─────────────────────────────────────────────────────────────────────────────

set -eo pipefail  # no -u: some bash/heredoc interactions trip unbound-var

API_BASE="${API_BASE:-http://localhost:8000}"
TOPIC_NAME="LLM Agents for Time-Series Reasoning"
RETRIEVAL=100
DEEP_READ=20
ROUNDS=3
QUICK=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick)       QUICK=true; shift ;;
    --topic)       TOPIC_NAME="$2"; shift 2 ;;
    --retrieval)   RETRIEVAL="$2"; shift 2 ;;
    --deep-read)   DEEP_READ="$2"; shift 2 ;;
    --rounds)      ROUNDS="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if $QUICK; then
  RETRIEVAL=10
  DEEP_READ=5
  ROUNDS=1
fi

PY=/opt/miniconda3/bin/python3
[ -x "$PY" ] || PY=python3

have_backend() {
  curl -sf "$API_BASE/api/topics" >/dev/null 2>&1
}

# ── 0. Pre-flight check ─────────────────────────────────────────────────────
if ! have_backend; then
  echo "ERROR: backend not reachable at $API_BASE" >&2
  echo "Start it with: $PY -m research_harness_mcp.http_api" >&2
  exit 1
fi

echo "▶ Demo target: $TOPIC_NAME"
echo "  Retrieval = $RETRIEVAL / Deep-read = $DEEP_READ / Rounds = $ROUNDS"
echo

# ── 1. Probe the agent pool ─────────────────────────────────────────────────
echo "▶ Resolving agent pool via llm_router.available_providers() ..."
$PY - <<'PYEOF'
from llm_router import available_providers
pool = available_providers()
print(f"  pool: {pool}")
print(f"  count: {len(pool)}")
PYEOF
echo

# ── 2. Create or find the topic ─────────────────────────────────────────────
# Write the topic list to a tmp file so Python can read stdin for argv and
# the JSON separately without the two fighting over fd 0.
topics_tmp=$(mktemp)
curl -sf "$API_BASE/api/topics" > "$topics_tmp" || echo '[]' > "$topics_tmp"
topic_id=$(TOPIC_NAME="$TOPIC_NAME" TOPICS_FILE="$topics_tmp" $PY -c '
import os, json
name = os.environ["TOPIC_NAME"]
try:
    data = json.load(open(os.environ["TOPICS_FILE"]))
except Exception:
    data = []
items = data if isinstance(data, list) else data.get("items", [])
for t in items:
    if isinstance(t, dict) and t.get("name") == name:
        print(t["id"]); break
')
rm -f "$topics_tmp"

if [ -z "$topic_id" ]; then
  echo "▶ Creating topic '$TOPIC_NAME' ..."
  create_resp=$(curl -s -X POST "$API_BASE/api/topics" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$TOPIC_NAME\", \"description\": \"$TOPIC_NAME\"}")
  topic_id=$(echo "$create_resp" | $PY -c "import sys,json
try: d=json.load(sys.stdin) or {}
except Exception: d={}
print(d.get('id',''))")
else
  echo "▶ Reusing topic $topic_id: $TOPIC_NAME"
fi

if [ -z "$topic_id" ]; then
  echo "ERROR: topic creation failed" >&2
  exit 1
fi

# ── 3. Show current topic state ─────────────────────────────────────────────
paper_count=$(curl -sf "$API_BASE/api/topics/$topic_id" \
  | $PY -c "import sys,json
try: d=json.load(sys.stdin) or {}
except Exception: d={}
print(d.get('paper_count',0))" 2>/dev/null || echo 0)
echo "▶ Topic has $paper_count papers (expansion's round 1 will fetch more)."
echo

# ── 4. Start expansion ──────────────────────────────────────────────────────
echo "▶ Starting expansion job: $RETRIEVAL retrieval / $DEEP_READ deep-read / $ROUNDS rounds ..."
start_resp=$(curl -sf -X POST "$API_BASE/api/topics/$topic_id/expansion" \
  -H "Content-Type: application/json" \
  -d "{\"retrieval_target\": $RETRIEVAL, \"deep_read_target\": $DEEP_READ, \"rounds\": $ROUNDS}")
echo "  $start_resp"
job_id=$(echo "$start_resp" | $PY -c "import sys,json;print(json.load(sys.stdin).get('job_id',''))")
echo

# ── 5. Monitor to completion ────────────────────────────────────────────────
echo "▶ Watching progress (updates every 15s; Ctrl-C to detach; job keeps running) ..."
i=0
while [ $i -lt 80 ]; do
  i=$((i + 1))
  state=$(curl -sf "$API_BASE/api/topics/$topic_id/expansion" 2>/dev/null || echo '{}')
  status_word=$(STATE="$state" $PY -c "$(cat <<'PYEOF'
import os, json
try:
    d = json.loads(os.environ.get('STATE') or '{}') or {}
except Exception:
    d = {}
status = d.get('status', '?')
rd = d.get('current_round', 0); rt = d.get('rounds_target', 0)
fd = d.get('papers_fetched', 0); ft = d.get('retrieval_target', 0)
dd = d.get('papers_deep_read', 0); dt = d.get('deep_read_target', 0)
tt = d.get('topic_paper_count', '?'); tdr = d.get('topic_deep_read_count', '?')
err = str(d.get('last_error') or '')[:80]
print('  [' + status.ljust(10) + '] round=' + str(rd) + '/' + str(rt)
      + ' fetched=' + str(fd) + '/' + str(ft)
      + ' deep=' + str(dd) + '/' + str(dt)
      + ' topic_count=' + str(tt) + ' topic_dr=' + str(tdr))
if err:
    print('    last_error: ' + err)
print('STATUS=' + status)
PYEOF
)")
  echo "$status_word" | grep -v "^STATUS="
  final=$(echo "$status_word" | grep "^STATUS=" | cut -d= -f2-)
  if [ "$final" = "completed" ] || [ "$final" = "failed" ] || [ "$final" = "cancelled" ]; then
    break
  fi
  sleep 15
done
echo

# ── 6. Summary & report ─────────────────────────────────────────────────────
echo "▶ Topic overview:"
topic_json=$(curl -sf "$API_BASE/api/topics/$topic_id" 2>/dev/null || echo '{}')
STATE="$topic_json" $PY -c "$(cat <<'PYEOF'
import os, json
try:
    d = json.loads(os.environ.get('STATE') or '{}') or {}
except Exception:
    d = {}
print('  name:        ' + str(d.get('name')))
print('  id:          ' + str(d.get('id')))
print('  paper_count: ' + str(d.get('paper_count')))
print('  (deep-read totals are in the expansion job summary below)')
PYEOF
)"

echo
echo "▶ Expansion job summary:"
exp_json=$(curl -sf "$API_BASE/api/topics/$topic_id/expansion" 2>/dev/null || echo '{}')
STATE="$exp_json" $PY -c "$(cat <<'PYEOF'
import os, json
try:
    d = json.loads(os.environ.get('STATE') or '{}') or {}
except Exception:
    d = {}
for k in ('id','status','retrieval_target','deep_read_target','rounds_target',
          'current_round','papers_fetched','papers_deep_read',
          'topic_paper_count','topic_deep_read_count','last_error'):
    v = d.get(k)
    if v is None:
        continue
    print('  ' + k.ljust(22) + ': ' + str(v))
PYEOF
)"
echo
echo "Done. Open http://localhost:3000/topics/$topic_id for the full dashboard view."
