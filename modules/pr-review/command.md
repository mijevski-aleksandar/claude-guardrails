---
description: Full PR review — three parallel focused agents (logic, security, style) followed by a verifier in the same session. Usage: /pr-review <PR_NUMBER>
argument-hint: PR number (e.g. 3404)
---

Review PR #${ARGUMENTS} end to end. No code modifications. Read-only.

## Step 1: Gather shared context (fetch once, share with all agents)

Identify the repo:
```bash
git remote get-url origin
```

Fetch PR metadata and extract the Shortcut story ID:
```bash
gh pr view ${ARGUMENTS} --json title,body,headRefName,baseRefName,author,url,files \
  | python3 -c "
import json, re, sys
pr = json.load(sys.stdin)
body = pr.get('body') or ''
branch = pr.get('headRefName') or ''
m = re.search(r'app\.shortcut\.com/[^/]+/story/(\d{4,})', body) \
    or re.search(r'\bsc-(\d{4,})\b', body, re.IGNORECASE) \
    or re.search(r'\bsc-(\d{4,})\b', branch, re.IGNORECASE)
print('STORY_ID=' + (m.group(1) if m else 'NONE'))
print('BASE=' + pr.get('baseRefName',''))
print('HEAD=' + branch)
print('TITLE=' + pr.get('title',''))
"
```

Write the diff to a temp file (agents will read from this path — do NOT use Read on it yourself):
```bash
gh pr diff ${ARGUMENTS} > /tmp/pr_diff_${ARGUMENTS}.txt
echo "Diff written to /tmp/pr_diff_${ARGUMENTS}.txt ($(wc -l < /tmp/pr_diff_${ARGUMENTS}.txt) lines)"
```

Fetch prior reviewer comments (both inline and top-level):
```bash
gh pr view ${ARGUMENTS} --json reviews,comments
gh api repos/<OWNER>/<REPO>/pulls/${ARGUMENTS}/comments
```

Read shared context files (use empty string if absent):
- `.claude/REVIEW.md`
- Root `CLAUDE.md`

Check for relevant project skills — REVIEW.md and CLAUDE.md capture general conventions, but enforcement details often live in a dedicated skill (e.g. an audit-logging or authorization skill) that documents a rule more precisely than REVIEW.md's prose. List `.claude/skills/*/SKILL.md`, skim each `description`/`when_to_use` frontmatter, and read the full contents of any skill whose scope overlaps the touched paths from Step 1's `files` list (e.g. a skill about views if a view file changed, one about audit logs if a mutating view changed, one about migrations if a migration changed). Pass the contents of any matched skill(s) to the reviewer agents alongside REVIEW.md/CLAUDE.md — do not rely on the agents to find and read these themselves.

**Stacked-PR check:** if BASE is not `main` (or the repo default — check `git symbolic-ref refs/remotes/origin/HEAD`), note it. The diff is against the immediate base, not main.

## Step 1.2: Check out the PR head into an isolated worktree

The reviewer agents and the verifier read source beyond the diff (model definitions, mixin MROs, settings, callers) and re-open files to confirm real line numbers. Your current branch is **not** the PR head, so those reads would resolve against the wrong code and produce wrong line numbers.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
WT="${TMPDIR:-/tmp}/claude-pr-review/$(basename "$REPO_ROOT")-pr-${ARGUMENTS}"
# Clear any stale worktree left by a crashed prior run.
git worktree remove --force "$WT" 2>/dev/null || true
git worktree prune
mkdir -p "$(dirname "$WT")"
git -C "$REPO_ROOT" fetch origin "pull/${ARGUMENTS}/head" \
  && git worktree add --detach "$WT" FETCH_HEAD \
  && echo "WORKTREE=$WT" \
  && git -C "$WT" log -1 --format='HEAD_SHA=%H %s'
```

`pull/N/head` resolves for fork PRs too — never check out `headRefName`, which may not exist on `origin` or may collide with a same-named local branch.

Uncommitted work in your current checkout is unaffected: `git worktree add` does not touch the current worktree's HEAD or index. This is why it must stay a worktree and not become a `git checkout`.

Confirm the checkout matches the PR before dispatching anything — compare `HEAD_SHA` against:
```bash
gh pr view ${ARGUMENTS} --json headRefOid --jq .headRefOid
```
If they differ the PR was force-pushed since Step 1; re-run `gh pr diff ${ARGUMENTS} > /tmp/pr_diff_${ARGUMENTS}.txt` so diff and worktree agree. This check is also what catches a cwd/PR repo mismatch, where `pull/N/head` could resolve to a *different* PR #N — treat it as a guard, not a nicety.

**If the worktree cannot be created** — fetch fails, head ref deleted, wrong repo, or a `git worktree lock`ed stale entry that `remove --force` won't clear: report which command failed and **stop**. Do not review the current branch as a fallback and do not auto-unlock; tell the user to run `git worktree unlock`. A review against the wrong tree yields confidently-wrong `file:line` claims that flow into `pr-verify-incoming` and become postable comments.

If the PR's `files` list from Step 1 includes `.claude/REVIEW.md`, root `CLAUDE.md`, or any `.claude/skills/*/SKILL.md`, re-read those from `<WORKTREE>` and use the worktree versions — the PR's own conventions govern the PR.

Record `WORKTREE`: pass it to every agent in Steps 3 and 5, and tear it down in Step 7.

## Step 1.5: Triage — decide fan-out vs single-pass

Check the diff size and touched paths:
```bash
gh pr diff ${ARGUMENTS} --patch | wc -l
gh pr view ${ARGUMENTS} --json files --jq '.files[].path'
```

If the diff is **under 50 changed lines** AND touches no migration file (`*/migrations/*`), no payment/refund code, and no NetSuite integration code (`*/netsuite/*`): skip Step 3's three-agent fan-out. Instead, do a single-pass inline review yourself against the same criteria the logic/security/style agents use (correctness, security, stated-convention violations only), then go directly to Step 5 with your own findings as the "structured findings" input.

When doing the single-pass review yourself, read source files from `<WORKTREE>` (Step 1.2), not from your current working directory — the same rule the agents get in Step 3 applies to you.

Otherwise, proceed with the full parallel fan-out below.

## Step 2: Fetch the Shortcut story

**If STORY_ID is NONE:** skip and record "Shortcut story: none referenced" for the verifier prompt.

**If STORY_ID is a number:**
1. `ToolSearch(query="select:mcp__shortcut__stories-get-by-id", max_results=1)`
2. `mcp__shortcut__stories-get-by-id(story_id="<STORY_ID>")`

If either call fails: record "Shortcut MCP unavailable" for the verifier prompt. Do not silently proceed.

## Step 3: Dispatch three reviewer agents in parallel

Launch all three in a **single message** (parallel, not sequential):

- **pr-review-logic** — pass: worktree path (`<WORKTREE>` from Step 1.2), diff file path (`/tmp/pr_diff_${ARGUMENTS}.txt`), REVIEW.md contents, CLAUDE.md contents, any matched skill contents from Step 1, prior reviewer comments table
- **pr-review-security** — pass: same inputs
- **pr-review-style** — pass: same inputs

Each agent prompt must tell the agent to read the diff from the file path. Do not inline the diff text in the agent prompt — the file path is the reference. Do not summarize or truncate.

Each agent prompt must also include this verbatim, with `<WORKTREE>` substituted:

> **Repository root for all file reads: `<WORKTREE>`.** This is a detached checkout of this PR's head commit. Every `Read`, `Grep`, and `Glob` for repository source must use a path under `<WORKTREE>` — prefix relative diff paths with it (diff path `slice_ops/models/liftoff.py` is `<WORKTREE>/slice_ops/models/liftoff.py`). This applies to confirming real line numbers, grepping for callers, and grepping for existing utilities to judge duplicate logic. Paths outside `<WORKTREE>` are a different branch and will give wrong content and wrong line numbers. The diff file is the one exception: it stays at `/tmp/pr_diff_${ARGUMENTS}.txt`. Do not run `git checkout`, `git switch`, or any state-changing git command.

Dispatch all three in one message and wait for every result in that single blocking step — do not use ScheduleWakeup to poll for completion. If an agent errors out, retry it once; if it fails again, tell the user immediately and proceed with the remaining agents' findings rather than silently dropping it. If you abort the review entirely, run Step 7's teardown first.

## Step 4: Collect and merge findings

Wait for all three agents to complete. Merge their outputs into a single numbered list:

```
| # | Agent | Asserted severity | File:line | Issue (one sentence) | Evidence snippet |
```

Deduplicate within this list: if two agents flagged the same file:line with the same root cause, keep one and note both agents.

If all three agents returned NO_FINDINGS, output:
> No issues found by any reviewer. PR appears clean.
> 
> (SC story: provided / unavailable / none referenced)

and stop — do not invoke the verifier. Run Step 7's teardown before emitting that message.

## Step 5: Invoke the verifier

Re-fetch reviewer comments before verifying — new comments may have landed while the reviewer agents were running:
```bash
gh pr view ${ARGUMENTS} --json reviews,comments
gh api repos/<OWNER>/<REPO>/pulls/${ARGUMENTS}/comments
```
Diff this against Step 1's earlier fetch; if there are new comments, include them.

Pass to **pr-verify-incoming** in this same session:

- PR number: ${ARGUMENTS}
- Worktree path: `<WORKTREE>` — **the repository root for all your file reads.** A detached checkout of this PR's head commit. Every `Read`/`Grep`/`Glob` against repository source must be a path under `<WORKTREE>`; prefix the relative `file:line` paths in the findings table with it before reading. This includes reading model definitions, tracing callers with `grep -rn`, and spot-checking claimed fixes. Reading elsewhere resolves against a different branch and yields wrong content and wrong line numbers. Do not run state-changing git commands.
- Repo: (from git remote)
- Structured findings: the merged table from Step 4
- Shortcut story: (title + description + AC from Step 2, or the unavailability note)
- Prior reviewer comments: (the refetched output above, including anything new since Step 1)

The verifier will grade each claim, apply tiered rigor by severity, deduplicate against prior comments, and produce ready-to-post GitHub comments for BLOCKING findings only.

## Step 6: Present results

Output the verifier's full response unchanged. Do not summarize, paraphrase, or editorialize. The verifier output is the final deliverable.

## Step 7: Tear down the worktree

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
git worktree remove --force "${TMPDIR:-/tmp}/claude-pr-review/$(basename "$REPO_ROOT")-pr-${ARGUMENTS}"
git worktree prune
```

Run this **before** emitting your final message, on every exit path: after Step 6's normal output, after Step 4's "no issues found" early stop, and after any abort (agent failures, missing findings, Shortcut/`gh` errors). If Step 1.2 succeeded, this must run. Safe to run twice, and safe if the worktree is already gone.
