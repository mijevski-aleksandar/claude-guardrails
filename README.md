# Claude Code Guardrails

> Modular hooks, agents, and commands for Claude Code — install only what you need, symlinked so edits here take effect immediately.

Works globally across **all your projects and windows** with per-module install.

---

## Install model: this repo is the live source of truth

`install.sh` creates **symlinks** from `~/.claude/{hooks,agents,commands}/` into this repo — it does not copy files. That means:

- Editing a file here is editing your live Claude Code config. No reinstall, no resync step.
- Uninstalling a module removes just its symlinks and its slice of `settings.json`, leaving everything else untouched.
- Each module is self-contained and independently installable — you don't have to take the whole set.

```bash
git clone https://github.com/mijevski-aleksandar/claude-guardrails.git
cd claude-guardrails

bash install.sh --list                    # see what's available
bash install.sh --install retry-loop      # install just one module
bash install.sh --install all             # install everything
```

To remove a module:

```bash
bash uninstall.sh --uninstall retry-loop
bash uninstall.sh --uninstall all
```

---

## Available modules

| Module | Type | What it does |
|---|---|---|
| `duplicate-reads` | hook | Blocks re-reads of the same bytes from an unchanged file (warn on 2nd, block on 3rd overlapping read) |
| `retry-loop` | hook | Detects and stops retry loops — exact and near-identical tool calls (warn on 1st repeat, block on 2nd) |
| `failed-tools` | hook | Detects tool failures via structured signals and escalates after repeated failures |
| `subagent-fanout-guard` | hook | Cost control against runaway parallel subagent spawns — warn at 3, block at 6 in-flight |
| `handoff-before-gap` | hook | Injects a brief recap prompt when resuming after a 30+ minute idle gap |
| `pr-review` | command + agents | `/pr-review <PR_NUMBER>` — three parallel reviewer agents (logic, security, style) + a verifier |

---

## Why This Exists

Claude Code can develop expensive habits mid-session, and long-lived multi-window setups surface problems generic hooks don't handle:

| Problem | What happens | Cost |
|---|---|---|
| **Duplicate reads** | Claude re-reads the same bytes of an unchanged file 4-5 times | 500-3000 wasted tokens per duplicate |
| **Retry loops** | Claude repeats the same failing call over and over | 200-2000 wasted tokens per loop |
| **Blind retries** | Tool failures aren't diagnosed before retrying | 1-5K wasted per failed retry |
| **Runaway subagent fan-out** | Each subagent cold-starts its own prompt-cache prefix (subagents can't share a cache prefix with each other) — spawning many at once is a real, direct cost driver, not free parallelism | Full cache-write cost per subagent |
| **Lost context after an idle gap** | Coming back to a session after a meeting/context-switch, Claude has no anchor for what it was doing | Time re-explaining state, or silent mistakes from stale assumptions |

Guardrails intercepts these patterns in real-time, warns or blocks the wasteful action, and tells Claude to adjust.

---

## Hooks

### `duplicate-reads`
**Fires:** `PreToolUse` on Read calls
**Warns:** On 2nd read of an overlapping byte range in an unchanged file
**Blocks:** On 3rd read of an overlapping byte range in an unchanged file (exit 2)

- **Byte-range tracking** — state is keyed on `file_path`, tracking which line ranges have already been read. Non-overlapping (legitimate paginated) reads never trigger a warning.
- **File change detection (mtime)** — if the file was modified since the last read, tracking resets and the read is allowed.
- **State namespaced per session** — see [Concurrency](#concurrency--shared-state) below.

**Config:** `WARN_AT` (default: 2), `BLOCK_AT` (default: 3) in `modules/duplicate-reads/hook.py`

---

### `retry-loop`
**Fires:** `PreToolUse` on tool calls (except Read/Grep/Glob, handled by `duplicate-reads`)
**Warns:** On 1st identical call (non-blocking)
**Blocks:** 2nd+ identical tool call

- **Bash normalization** — ignores the `description` field, so retrying the same command with a different description is still caught.
- **ExitPlanMode count-based tracking** — tracked by invocation count, not content fingerprint, since editing the plan slightly between attempts doesn't evade it. Warns on 2nd, blocks on 3rd.
- **Tightened from 3→2** — real session evidence showed warn-only rarely changed behavior; blocking earlier reduces wasted calls before the guardrail has any effect.

**Config:** `MAX_IDENTICAL` (default: 2), `WARN_AT` (default: 1), `EPM_MAX`/`EPM_WARN` for ExitPlanMode in `modules/retry-loop/hook.py`

---

### `failed-tools`
**Fires:** `PostToolUse` on every tool call
**On any failure:** Warns Claude to diagnose before retrying
**After 3 failures:** Escalates — forces Claude to list failures and ask for help

Detects real failures using structured signals: a top-level `is_error` flag, a dict-shaped `tool_response` with `is_error`/`exitCode`, or a string response starting with `Error:`, `Exit code <n>` (n≠0), or `<tool_use_error>`. The exact field shape was verified against real session transcripts — earlier versions checked fields/prefixes that didn't match how failures actually surface, so this hook never fired in practice until fixed.

**Config:** `MAX_FAILURES` (default: 3) in `modules/failed-tools/hook.py`

---

### `subagent-fanout-guard`
**Fires:** `SubagentStart`/`SubagentStop` (track in-flight count), `PreToolUse` on the `Agent` tool (enforce)
**Warns:** When ≥3 subagents are already in flight before allowing another spawn
**Blocks:** When ≥6 are already in flight (exit 2)

Subagents cannot share a prompt-cache prefix with each other or the parent — each spawn pays its own cache-write cost. `SubagentStart`/`SubagentStop` can't block directly (no exit-2 support on Start; Stop's exit-2 only prevents that one subagent from stopping), so enforcement happens on `PreToolUse` for the `Agent` tool call that would create the next one.

**Config:** `WARN_AT` (default: 3), `MAX` (default: 6) in `modules/subagent-fanout-guard/hook.py`

---

### `handoff-before-gap`
**Fires:** `Stop` (stamp timestamp), `UserPromptSubmit` (check gap, inject recap instruction)
**Threshold:** 30 minutes idle
**Never blocks** — advisory context injection only, always exits 0.

Replaces the intent of an earlier `PreCompact`-based handoff design that broke silently: that design depended on hook *ordering* within the `PreCompact` chain, and a separate blocking hook placed earlier in that chain (`compaction_guard.py`, never part of this repo) silently prevented the rest of the chain from running for months. This hook is anchored to `Stop`/`UserPromptSubmit` instead — both fire on every turn regardless of what else is happening, so there's no ordering dependency to get wrong. When the gap since the last `Stop` exceeds the threshold, it injects `additionalContext` asking Claude to open its next reply with a 2-3 sentence recap of where things stood before addressing the new message.

**Config:** `GAP_THRESHOLD_SECONDS` (default: 1800) in `modules/handoff-before-gap/hook.py`

---

## `pr-review`

`/pr-review <PR_NUMBER>` — fans out three parallel reviewer agents (`pr-review-logic`, `pr-review-security`, `pr-review-style`) against the PR diff, then a verifier agent (`pr-verify-incoming`) grades every finding against the actual code before anything gets posted. See `modules/pr-review/command.md` and `modules/pr-review/agents/` for the full agent prompts.

Designed to minimize false positives reaching a real PR: findings are only surfaced as ready-to-post comments after independent verification, with tiered rigor by severity and deduplication against prior reviewer comments.

---

## Concurrency — shared state

Every hook that needs state uses `shared/state_paths.py`, which namespaces state files per session: `/tmp/claude-guardrails/<hook_name>/<session_id>.json`. Concurrent Claude Code sessions (multiple windows, multiple repos open at once) each get their own file — no more resetting each other's counters via a shared global file keyed by a single `session_id` field, which is what earlier versions of these hooks did.

---

## Design Principles

1. **Never degrade output** — every block has a legitimate-reason escape hatch.
2. **Warn before blocking** where the action isn't immediately costly; block sooner where warnings demonstrably don't change behavior (see `retry-loop`'s tightened threshold).
3. **Block messages always say what to do instead.**
4. **Zero maintenance** — state is per-session, no manual cleanup.
5. **Each module stands alone** — no module depends on another module's hook logic, only on the shared `state_paths.py` helper.

---

## Changelog — retired hooks

Earlier versions of this repo included `context_pressure.py`, `compaction_reset.py`, `session_summary.py`, `post_compact.py`, and `pre_compact.py`. All five were removed:

- **`context_pressure.py`** — warn-only by design (step-count nagging at 50/80 steps), with no enforcement. Real session evidence showed a session hit its "critical" warning 33 times across 33 steps with zero behavioral change — it was pure noise.
- **`pre_compact.py` / `compaction_reset.py` / `session_summary.py` / `post_compact.py`** — this `PreCompact`/`PostCompact` chain wrote a session handoff (`last-session.md`) intended to preserve context across compaction. In practice, a separate local-only hook (never part of this repo) ran first in the `PreCompact` chain and blocked compaction outright for any non-trivial session — which silently prevented the rest of the chain, including the handoff write, from running at all for months. Rather than fix the ordering dependency, the whole approach was retired in favor of `handoff-before-gap`, which doesn't depend on `PreCompact` ordering at all.

---

## Customising

Each hook's config lives at the top of its `modules/<name>/hook.py`. Edit and save — no restart needed, hooks are loaded fresh on each invocation.

## Contributing

See `.github/CONTRIBUTING.md`. To add a new module: create `modules/<name>/` with a `module.json` (declaring what gets symlinked where) and, if it needs one, a `settings.fragment.json` (the hook-event fragment to merge into `settings.json`).
