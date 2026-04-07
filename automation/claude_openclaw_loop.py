import subprocess
import re
from pathlib import Path

ROOT = Path.cwd()
TMP = ROOT / "automation" / "tmp"
TMP.mkdir(parents=True, exist_ok=True)

CLAUDE_CMD = [
    "claude",
    "-p",
    "--permission-mode",
    "bypassPermissions",
    "--tools",
    "default",
    "--add-dir",
    "/Users/manto/Projects/careeros",
]

OPENCLAW_CMD = [
    "npx",
    "pnpm",
    "openclaw",
    "--profile",
    "dev",
    "agent",
    "--agent",
    "main",
]

BOOTSTRAP = """
You are in AUTONOMOUS BUILD MODE.

Rules:
1. Work on one roadmap item at a time.
2. After each implementation step, run tests.
3. Always return these exact sections:

=== PROGRESS UPDATE ===
- features completed
- files modified
- tests status
- next roadmap item

=== QA HANDOFF ===
- Changed files:
- Changed features:
- APIs to test:
- Pages to test:
- Files to upload/test:
- Expected behavior:
- Known risks:
- Need restart: yes/no
- Need rebuild: yes/no
- Need migration: yes/no

=== OPENCLAW PROMPT ===
[a complete OpenClaw prompt here]
=== END OPENCLAW PROMPT ===

4. If OpenClaw says PASS, continue to the next roadmap item.
5. If OpenClaw says FAIL / WEAK TRUST / WEAK INTELLIGENCE, fix only the reported issues.
6. Do not redesign the architecture unless explicitly asked.
7. Keep changes minimal and production-oriented.
"""

def run(cmd, stdin=None, cwd=None):
    proc = subprocess.run(
        cmd,
        input=stdin,
        text=True,
        capture_output=True,
        cwd=cwd,
    )
    return proc.returncode, proc.stdout, proc.stderr

def run_claude(prompt: str) -> str:
    full_prompt = BOOTSTRAP + "\n\n" + prompt
    code, out, err = run(CLAUDE_CMD, stdin=full_prompt)
    text = (out or "") + ("\n" + err if err else "")
    (TMP / "claude_output.txt").write_text(text)
    if code != 0:
        raise RuntimeError(f"Claude failed:\n{text}")
    return text

def extract_openclaw_prompt(text: str) -> str:
    m = re.search(
        r"=== OPENCLAW PROMPT ===\s*(.*?)\s*=== END OPENCLAW PROMPT ===",
        text,
        re.S,
    )
    if not m:
        raise ValueError("Could not find OPENCLAW PROMPT block.")
    prompt = m.group(1).strip()
    (TMP / "openclaw_prompt.txt").write_text(prompt)
    return prompt

def run_openclaw(prompt: str) -> str:
    cmd = OPENCLAW_CMD + ["--message", prompt]
    code, out, err = run(cmd, cwd="/Users/manto/openclaw")
    text = (out or "") + ("\n" + err if err else "")
    (TMP / "openclaw_report.txt").write_text(text)
    return text

def extract_status(report: str) -> str:
    m = re.search(r"STATUS:\s*(PASS|FAIL|WEAK TRUST|WEAK INTELLIGENCE)", report, re.I)
    return m.group(1).upper() if m else "UNKNOWN"

def main():
    prompt = """
Continue the StealthRole roadmap from the current state.

Work on one roadmap item at a time.
After each item:
- run tests
- generate QA HANDOFF
- generate OPENCLAW PROMPT
- wait for OpenClaw result
- fix issues if any
- then continue
"""

    for i in range(1, 9):
        print(f"\n========== ITERATION {i} ==========\n")

        claude_text = run_claude(prompt)
        print(claude_text)

        oc_prompt = extract_openclaw_prompt(claude_text)
        print("\n--- Running OpenClaw ---\n")

        oc_report = run_openclaw(oc_prompt)
        print(oc_report)

        status = extract_status(oc_report)
        print(f"\nOpenClaw STATUS: {status}\n")

        if status == "PASS":
            prompt = """
OpenClaw passed.

Proceed to the next roadmap item.
Return:
=== PROGRESS UPDATE ===
=== QA HANDOFF ===
=== OPENCLAW PROMPT ===
"""
        else:
            prompt = f"""
Fix the issues found by OpenClaw.

Rules:
- prioritize critical failures first
- do not add new features
- keep changes minimal
- run tests again
- then return:
=== PROGRESS UPDATE ===
=== QA HANDOFF ===
=== OPENCLAW PROMPT ===

OPENCLAW REPORT:
{oc_report}
"""

    print("\nLoop finished. Check automation/tmp for outputs.")

if __name__ == "__main__":
    main()
