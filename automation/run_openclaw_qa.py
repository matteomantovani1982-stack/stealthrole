#!/usr/bin/env python3
"""
run_openclaw_qa.py — Python version of the Claude↔OpenClaw QA bridge.

Two modes:
  python3 automation/run_openclaw_qa.py              # full: send prompt + generate fix input
  python3 automation/run_openclaw_qa.py --report-only # just parse existing report → fix input

Reads:  tmp/openclaw_prompt.txt   (the prompt Claude wrote)
        tmp/openclaw_report.txt   (OpenClaw's response)
Writes: tmp/openclaw_report.txt   (if running full mode)
        tmp/claude_fix_input.txt  (always)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
PROMPT_FILE = SCRIPT_DIR / "tmp" / "openclaw_prompt.txt"
REPORT_FILE = SCRIPT_DIR / "tmp" / "openclaw_report.txt"
FIX_FILE = SCRIPT_DIR / "tmp" / "claude_fix_input.txt"
OPENCLAW_DIR = Path.home() / "openclaw"

PASS_TEMPLATE = """OpenClaw passed. All checks green.

Proceed to the next roadmap item.
Return QA HANDOFF and OPENCLAW PROMPT for the next feature.
"""

FIX_TEMPLATE = """Fix these issues found by OpenClaw.

OPENCLAW REPORT:
{report}

Rules:
- fix only the reported issues
- keep changes minimal
- do not rewrite unrelated code
- re-run smoke tests
- return updated QA HANDOFF and OPENCLAW PROMPT
"""


def send_to_openclaw(prompt: str) -> str | None:
    """Try to send prompt to OpenClaw. Returns response or None."""
    # Method 1: global CLI
    if _which("openclaw"):
        print("Using: openclaw CLI")
        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            return result.stdout
        print(f"openclaw CLI failed: {result.stderr[:200]}")

    # Method 2: npx in repo
    if OPENCLAW_DIR.is_dir():
        print(f"Using: npx in {OPENCLAW_DIR}")
        result = subprocess.run(
            ["npx", "pnpm", "openclaw", "--profile", "dev",
             "agent", "--agent", "main", "--message", prompt],
            capture_output=True, text=True, timeout=300,
            cwd=str(OPENCLAW_DIR),
        )
        if result.returncode == 0:
            return result.stdout
        print(f"npx openclaw failed: {result.stderr[:200]}")

    # Method 3: stdin pipe approach (for large prompts)
    if _which("openclaw"):
        print("Trying: stdin pipe approach")
        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", "-"],
            input=prompt, capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            return result.stdout

    return None


def generate_fix_input():
    """Read the report and generate claude_fix_input.txt."""
    if not REPORT_FILE.exists():
        print(f"ERROR: {REPORT_FILE} not found. Run OpenClaw first.")
        sys.exit(1)

    report = REPORT_FILE.read_text().strip()
    if not report:
        print(f"ERROR: {REPORT_FILE} is empty.")
        sys.exit(1)

    # Detect PASS/FAIL
    is_pass = "STATUS: PASS" in report.upper() or "ALL CHECKS PASSED" in report.upper()

    if is_pass:
        FIX_FILE.write_text(PASS_TEMPLATE)
        print(f"\n{'='*50}")
        print("  STATUS: PASS")
        print(f"  Written to: {FIX_FILE}")
        print(f"{'='*50}")
        print("\nNext: paste claude_fix_input.txt content to Claude")
        print("      or just tell Claude to proceed with the roadmap.")
    else:
        fix_content = FIX_TEMPLATE.format(report=report)
        FIX_FILE.write_text(fix_content)
        print(f"\n{'='*50}")
        print("  STATUS: FAIL")
        print(f"  Written to: {FIX_FILE}")
        print(f"{'='*50}")
        print("\nNext: paste claude_fix_input.txt content to Claude")
        print("      Claude will fix the issues and generate a new OPENCLAW PROMPT.")

    return is_pass


def _which(cmd: str) -> bool:
    """Check if a command exists on PATH."""
    return subprocess.run(
        ["which", cmd], capture_output=True
    ).returncode == 0


def main():
    report_only = "--report-only" in sys.argv

    if not report_only:
        # Full mode: read prompt, send to OpenClaw, save report
        if not PROMPT_FILE.exists():
            print(f"ERROR: {PROMPT_FILE} not found.")
            print("Claude must write the OPENCLAW PROMPT to this file first.")
            sys.exit(1)

        prompt = PROMPT_FILE.read_text().strip()
        if not prompt:
            print(f"ERROR: {PROMPT_FILE} is empty.")
            sys.exit(1)

        print("=== OpenClaw QA Bridge (Python) ===")
        print(f"Prompt: {len(prompt)} chars, {prompt.count(chr(10))+1} lines")
        print()

        response = send_to_openclaw(prompt)

        if response is None:
            print()
            print("=" * 50)
            print("  OpenClaw CLI not available.")
            print("  Manual mode:")
            print()
            print(f"  1. Copy prompt from: {PROMPT_FILE}")
            print(f"  2. Run it in OpenClaw manually")
            print(f"  3. Paste the report into: {REPORT_FILE}")
            print(f"  4. Run: python3 automation/run_openclaw_qa.py --report-only")
            print("=" * 50)
            return

        REPORT_FILE.write_text(response)
        print(f"Report saved to: {REPORT_FILE}")

    # Parse report and generate fix input
    generate_fix_input()


if __name__ == "__main__":
    main()
