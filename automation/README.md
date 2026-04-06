# Claude ↔ OpenClaw QA Bridge

Minimal local automation to reduce copy/paste between Claude and OpenClaw.

## How It Works

```
Claude implements feature
    ↓ writes
tmp/openclaw_prompt.txt
    ↓ script sends to OpenClaw
tmp/openclaw_report.txt
    ↓ script generates
tmp/claude_fix_input.txt
    ↓ you paste to Claude
Claude fixes issues → new prompt → repeat
```

## Files

```
automation/
  run_openclaw_qa.sh     # shell version (tries CLI, falls back to manual)
  run_openclaw_qa.py     # python version (same logic, more robust)
  README.md              # this file

tmp/
  openclaw_prompt.txt    # Claude writes this after each feature
  openclaw_report.txt    # OpenClaw's structured QA report
  claude_fix_input.txt   # Generated: paste this to Claude if FAIL
```

## Usage

### Step 1: Claude writes the prompt

After implementing a feature, Claude writes the `=== OPENCLAW PROMPT ===` section
and also saves it to `tmp/openclaw_prompt.txt`.

### Step 2: Run the bridge

**Automatic** (if OpenClaw CLI is available):
```bash
./automation/run_openclaw_qa.sh
# or
python3 automation/run_openclaw_qa.py
```

**Manual** (if OpenClaw CLI is not available):
```bash
# 1. Copy the prompt
cat tmp/openclaw_prompt.txt

# 2. Run it in OpenClaw (web UI or CLI)

# 3. Paste the report
pbpaste > tmp/openclaw_report.txt
# or manually save OpenClaw's output to tmp/openclaw_report.txt

# 4. Generate the fix input
python3 automation/run_openclaw_qa.py --report-only
```

### Step 3: Feed results back to Claude

If **PASS**:
```
cat tmp/claude_fix_input.txt
# → "OpenClaw passed. Proceed to next roadmap item."
# → Tell Claude to continue
```

If **FAIL**:
```
cat tmp/claude_fix_input.txt
# → Contains the full report + fix instructions
# → Paste this to Claude
# → Claude fixes issues and writes a new openclaw_prompt.txt
# → Repeat from Step 2
```

## OpenClaw Report Format

OpenClaw must return this structure:

```
STATUS: PASS / FAIL

FAILED CHECKS:
- ...

REASONING ISSUES:
- ...

SCORING ISSUES:
- ...

ENDPOINT ISSUES:
- ...

SUMMARY:
- total checks run: N
- total failures: N
- recommended fixes: ...
```

## Recovery

**OpenClaw is down / queued:**
- Save your prompt in `tmp/openclaw_prompt.txt`
- Continue coding other features
- Run QA later when OpenClaw is available

**Report looks wrong:**
- Edit `tmp/openclaw_report.txt` manually
- Re-run `python3 automation/run_openclaw_qa.py --report-only`

**Multiple features pending QA:**
- QA them in order
- Each cycle overwrites the tmp files
- If you need history, copy files before the next run:
  `cp tmp/openclaw_report.txt tmp/openclaw_report_shadow.txt`
