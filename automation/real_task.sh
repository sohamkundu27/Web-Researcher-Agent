#!/usr/bin/env bash
#
# real_task.sh — one genuine maintenance pass on Web-Researcher-Agent.
#
# Fired a few times a day by cron. Each run:
#   1. picks the next subtopic (rotation, no repeat until the list cycles),
#   2. asks Claude Code (Haiku, hard $ budget cap) to make ONE real improvement,
#   3. gates on the test suite: commits only if pytest passes AND something
#      actually changed; otherwise reverts and commits nothing.
#
# No template text, no randomized skip. Some runs legitimately produce no
# commit (nothing worth doing / tests failed) — that is expected and honest.
#
# Setup: edit REPO_PATH below if you move the repo. Everything else is derived.

set -euo pipefail

# ---- config -----------------------------------------------------------------
REPO_PATH="/home/soham/Web-Researcher-Agent"
MODEL="haiku"                 # cheapest model; alias tracks the latest Haiku
MAX_BUDGET_USD="0.50"         # hard per-run spend cap (claude --max-budget-usd)
RUN_TIMEOUT_SECS="900"        # wall-clock safety timeout for the Claude call
DO_PUSH="true"               # `git push` after a successful commit (set false for local-only)

RUNTIME_DIR="$HOME/.web-researcher-agent"
VENV="$RUNTIME_DIR/venv"
STATE_FILE="$RUNTIME_DIR/last_subtopic_index"
LOG_FILE="$RUNTIME_DIR/cron.log"
OUTPUT_FILE="$RUNTIME_DIR/last_run_output.txt"

SUBTOPICS_FILE="$REPO_PATH/automation/subtopics.txt"
TEMPLATE_FILE="$REPO_PATH/automation/task_prompt_template.txt"

# Minimal deps needed to import src/ and run the test suite (kept lightweight;
# the full requirements.txt has heavy extras the tests don't need).
TEST_DEPS=(pytest anthropic requests beautifulsoup4 python-dotenv flake8 black)

# Only these paths are ever staged/committed or reverted — keeps automated
# commits scoped to real project content and never touches automation/ or venv.
COMMIT_PATHS=(src tests examples docs README.md Makefile setup.py pytest.ini .flake8 requirements.txt)

# Make cron's minimal environment find node/claude/git.
export PATH="/home/soham/.nvm/versions/node/v24.16.0/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
# Non-interactive SSH for `git push` from cron: never prompt for passphrase or
# host-key confirmation (origin is git@github.com; key has no passphrase).
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude || echo /home/soham/.nvm/versions/node/v24.16.0/bin/claude)}"

DRY_RUN="${DRY_RUN:-false}"   # DRY_RUN=true skips the Claude call and any commit

# ---- helpers ----------------------------------------------------------------
mkdir -p "$RUNTIME_DIR"
log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }

# Restore the working tree to a pristine HEAD within project paths only.
tidy() {
  git -C "$REPO_PATH" reset --hard HEAD >/dev/null 2>&1 || true
  git -C "$REPO_PATH" clean -fd -- "${COMMIT_PATHS[@]}" >/dev/null 2>&1 || true
}

# ---- preflight --------------------------------------------------------------
[ -d "$REPO_PATH/.git" ]     || die "REPO_PATH is not a git repo: $REPO_PATH"
[ -f "$SUBTOPICS_FILE" ]     || die "missing subtopics file: $SUBTOPICS_FILE"
[ -f "$TEMPLATE_FILE" ]      || die "missing prompt template: $TEMPLATE_FILE"
[ -x "$CLAUDE_BIN" ]         || die "claude CLI not found/executable: $CLAUDE_BIN"

cd "$REPO_PATH"

# Refuse to run on top of un-committed work to tracked files (protects real WIP).
# Untracked files (e.g. an as-yet-uncommitted automation/ dir) do not block us.
if ! git diff --quiet || ! git diff --cached --quiet; then
  die "working tree has uncommitted changes to tracked files; aborting to avoid mixing"
fi

# venv bootstrap (idempotent; only installs on first run).
if [ ! -x "$VENV/bin/python" ]; then
  log "bootstrapping venv at $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
  "$VENV/bin/pip" install -q "${TEST_DEPS[@]}" || die "venv dependency install failed"
fi
# Put the venv first so Claude's own pytest/flake8/black use the right deps.
export PATH="$VENV/bin:$PATH"

# ---- subtopic rotation ------------------------------------------------------
mapfile -t SUBTOPICS < <(grep -vE '^\s*(#|$)' "$SUBTOPICS_FILE")
N="${#SUBTOPICS[@]}"
[ "$N" -gt 0 ] || die "no subtopics defined in $SUBTOPICS_FILE"

LAST_IDX="$(cat "$STATE_FILE" 2>/dev/null || echo -1)"
[[ "$LAST_IDX" =~ ^-?[0-9]+$ ]] || LAST_IDX=-1
IDX=$(( (LAST_IDX + 1) % N ))
SUBTOPIC="${SUBTOPICS[$IDX]}"
echo "$IDX" > "$STATE_FILE"

log "run start | subtopic[$IDX/$((N-1))]: $SUBTOPIC"

# ---- build prompt -----------------------------------------------------------
# Substitute {{SUBTOPIC}} without risking regex/delimiter issues.
PROMPT="$(SUBTOPIC="$SUBTOPIC" python3 - "$TEMPLATE_FILE" <<'PY'
import os, sys
with open(sys.argv[1]) as f:
    print(f.read().replace("{{SUBTOPIC}}", os.environ["SUBTOPIC"]), end="")
PY
)"

if [ "$DRY_RUN" = "true" ]; then
  log "DRY_RUN=true — skipping Claude call and commit. Prompt preview:"
  printf '%s\n' "$PROMPT" | sed 's/^/    /' | tee -a "$LOG_FILE"
  log "run end (dry run)"
  exit 0
fi

# ---- run Claude Code (headless, budget-capped) ------------------------------
BASE_REF="$(git rev-parse HEAD)"
set +e
timeout "$RUN_TIMEOUT_SECS" "$CLAUDE_BIN" -p "$PROMPT" \
  --model "$MODEL" \
  --max-budget-usd "$MAX_BUDGET_USD" \
  --permission-mode acceptEdits \
  --allowedTools Edit Write Read Grep Glob \
    "Bash(pytest:*)" "Bash(python -m pytest:*)" \
    "Bash(flake8:*)" "Bash(python -m flake8:*)" \
    "Bash(black:*)" "Bash(python -m black:*)" \
  --disallowedTools WebFetch WebSearch \
  --output-format text \
  > "$OUTPUT_FILE" 2>>"$LOG_FILE"
CLAUDE_RC=$?
set -e
[ "$CLAUDE_RC" -eq 0 ] || log "note: claude exited $CLAUDE_RC (budget/timeout/other) — proceeding to gate on results anyway"

# Restrict to committable paths that actually exist right now (a subtopic may
# have just created e.g. docs/). `git add` fatals on a non-matching pathspec, so
# we must never hand it one — that would abort the run under `set -e`.
EXIST_PATHS=()
for p in "${COMMIT_PATHS[@]}"; do [ -e "$REPO_PATH/$p" ] && EXIST_PATHS+=("$p"); done
[ "${#EXIST_PATHS[@]}" -gt 0 ] || die "no committable paths exist (unexpected)"

# ---- change detection -------------------------------------------------------
if git diff --quiet -- "${EXIST_PATHS[@]}" && \
   [ -z "$(git ls-files --others --exclude-standard -- "${EXIST_PATHS[@]}")" ]; then
  log "no change produced for this subtopic — nothing to commit (this is fine)"
  tidy
  log "run end (no change)"
  exit 0
fi

# ---- test gate --------------------------------------------------------------
log "changes detected — running test gate (pytest)"
if ! "$VENV/bin/python" -m pytest tests/ -q >>"$LOG_FILE" 2>&1; then
  log "TEST GATE FAILED — reverting all changes, committing nothing"
  tidy
  log "run end (reverted)"
  exit 0
fi
log "test gate passed"

# flake8 is advisory only (the baseline tree already has known violations).
# flake8 exits non-zero on findings; the brace-group + `|| true` keeps that from
# tripping `set -e`/`pipefail` and aborting the run before the commit.
FLAKE_COUNT="$({ "$VENV/bin/flake8" src tests examples 2>/dev/null || true; } | wc -l | tr -d ' ')"
log "flake8 (advisory): $FLAKE_COUNT finding(s) in tree after change"

# ---- commit -----------------------------------------------------------------
# Commit subject = Claude's final summary line, sanitized; strip CHANGE:/NO CHANGE: tag.
RAW_SUBJECT="$(grep -v '^\s*$' "$OUTPUT_FILE" | tail -n 1 || true)"
SUBJECT="$(printf '%s' "$RAW_SUBJECT" | sed -E 's/^\s*(CHANGE|NO CHANGE):\s*//I' | tr -d '\r' | cut -c1-65)"
[ -n "$SUBJECT" ] || SUBJECT="maintenance pass"

git add -- "${EXIST_PATHS[@]}"
if git diff --cached --quiet; then
  log "changes were outside committable paths — nothing staged; reverting"
  tidy
  log "run end (no committable change)"
  exit 0
fi

git commit -q -m "${SUBJECT}" -m "Subtopic: ${SUBTOPIC}
Run: $(date -Iseconds)
Verified: pytest suite passing; flake8 advisory=${FLAKE_COUNT}"

NEW_REF="$(git rev-parse --short HEAD)"
log "committed ${NEW_REF}: ${SUBJECT}"

if [ "$DO_PUSH" = "true" ]; then
  if git push >>"$LOG_FILE" 2>&1; then
    log "pushed to $(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo origin)"
  else
    log "WARNING: git push failed (commit is safe locally); see log"
  fi
fi

# Ensure a pristine tree for the next run (drops any stray leftovers).
git reset --hard HEAD >/dev/null 2>&1 || true
git clean -fd -- "${COMMIT_PATHS[@]}" >/dev/null 2>&1 || true
log "run end (committed${DO_PUSH:+, push=$DO_PUSH})"
