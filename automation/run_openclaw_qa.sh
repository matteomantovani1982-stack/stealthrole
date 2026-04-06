#!/bin/zsh
#
# run_openclaw_qa.sh — minimal Claude↔OpenClaw QA bridge
#
# Usage:
#   ./automation/run_openclaw_qa.sh
#
# Reads:  tmp/openclaw_prompt.txt
# Writes: tmp/openclaw_report.txt
#         tmp/claude_fix_input.txt
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROMPT_FILE="$SCRIPT_DIR/tmp/openclaw_prompt.txt"
REPORT_FILE="$SCRIPT_DIR/tmp/openclaw_report.txt"
FIX_FILE="$SCRIPT_DIR/tmp/claude_fix_input.txt"

# ── Preflight ────────────────────────────────────────────────────────────────

if [[ ! -f "$PROMPT_FILE" ]]; then
    echo "ERROR: $PROMPT_FILE not found."
    echo "Claude must write the OPENCLAW PROMPT to this file first."
    exit 1
fi

PROMPT=$(cat "$PROMPT_FILE")
if [[ -z "$PROMPT" ]]; then
    echo "ERROR: $PROMPT_FILE is empty."
    exit 1
fi

echo "=== OpenClaw QA Bridge ==="
echo "Prompt file: $PROMPT_FILE ($(wc -l < "$PROMPT_FILE") lines)"
echo ""

# ── Send to OpenClaw ─────────────────────────────────────────────────────────
# Attempts three methods in order:
#   1. openclaw CLI (if installed globally)
#   2. npx in ~/openclaw repo
#   3. Manual fallback (copy/paste instructions)

OPENCLAW_DIR="$HOME/openclaw"

send_openclaw() {
    # Method 1: global CLI
    if command -v openclaw &>/dev/null; then
        echo "Using: openclaw CLI"
        openclaw agent --agent main --message "$PROMPT" 2>&1
        return $?
    fi

    # Method 2: npx in repo
    if [[ -d "$OPENCLAW_DIR" ]]; then
        echo "Using: npx in $OPENCLAW_DIR"
        cd "$OPENCLAW_DIR"
        npx pnpm openclaw --profile dev agent --agent main --message "$PROMPT" 2>&1
        return $?
    fi

    # Method 3: manual fallback
    return 1
}

echo "Sending prompt to OpenClaw..."
echo ""

if RESPONSE=$(send_openclaw 2>&1); then
    echo "$RESPONSE" > "$REPORT_FILE"
    echo "Report saved to: $REPORT_FILE"
else
    echo ""
    echo "============================================"
    echo "  OpenClaw CLI not available."
    echo "  Manual mode: copy the prompt below,"
    echo "  run it in OpenClaw, paste the report into:"
    echo "  $REPORT_FILE"
    echo "============================================"
    echo ""
    echo "--- PROMPT START ---"
    cat "$PROMPT_FILE"
    echo "--- PROMPT END ---"
    echo ""
    echo "After pasting the report into $REPORT_FILE, run:"
    echo "  python3 automation/run_openclaw_qa.py --report-only"
    exit 0
fi

# ── Generate Claude fix input ────────────────────────────────────────────────

python3 "$SCRIPT_DIR/automation/run_openclaw_qa.py" --report-only
