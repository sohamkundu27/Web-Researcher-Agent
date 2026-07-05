# automation/ — genuine maintenance loop

A small cron-driven loop that runs a real maintenance pass on this repo a few
times a day. Every commit reflects actual, test-verified work. There is **no**
filler, no template text, and no randomized skip — some runs simply produce no
commit, and that's expected.

## Files

| File | Purpose |
|------|---------|
| `subtopics.txt` | Rotating list of genuine work areas. Edit freely. |
| `task_prompt_template.txt` | The per-run prompt (`{{SUBTOPIC}}` is filled in). |
| `real_task.sh` | The runner: rotate → Claude (Haiku) → **pytest gate** → commit. |

## What one run does

1. Picks the next subtopic (sequential rotation — cycles through all before repeating).
2. Aborts if the tree has uncommitted changes to tracked files (protects your WIP).
3. Asks Claude Code (`--model haiku`, hard `--max-budget-usd 0.50`) to make **one**
   small, real improvement in that subtopic — or nothing, if nothing's worth doing.
4. **Gate:** if files changed, runs the full `pytest` suite.
   - pass + real diff → commit (scoped to project paths only).
   - tests fail → revert everything, commit nothing.
   - no diff → commit nothing.
   - `flake8` is advisory (logged, non-blocking — the baseline tree already has findings).

## Runtime state (outside the repo, at `~/.web-researcher-agent/`)

- `venv/` — isolated Python env for the test gate (auto-created on first run)
- `last_subtopic_index` — rotation pointer
- `cron.log` — full run log  ·  `last_run_output.txt` — Claude's last output

## Configure

Edit the vars at the top of `real_task.sh`:

- `REPO_PATH` — repo location (already set)
- `MAX_BUDGET_USD` — per-run spend cap (default `0.50`)
- `DO_PUSH` — `false` by default (local commits only); set `true` to push after commit

## Install cron (3×/day, spread out)

```cron
0 9,13,17 * * * /bin/bash /home/soham/Web-Researcher-Agent/automation/real_task.sh
```

## Try it safely first

```bash
DRY_RUN=true bash automation/real_task.sh   # no Claude call, no commit — just rotation + prompt
tail -f ~/.web-researcher-agent/cron.log
```
