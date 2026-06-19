---
name: karpathy-coding-guidelines
description: >-
  Applies Karpathy-style agent discipline for coding: surface assumptions and
  tradeoffs, prefer minimal solutions, limit diffs to the request, and define
  verifiable success criteria with tests. Use for non-trivial implementation,
  refactors, bug fixes, code review, or when the user asks for simple PRs,
  surgical changes, or less overengineering.
---

# Karpathy-inspired coding guidelines

Behavioral rules adapted from [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) (upstream `CLAUDE.md`). Merge with project rules; they bias toward **caution over speed**—use judgment on trivial one-liners.

## 1. Think before coding

**Do not assume. Do not hide confusion. Surface tradeoffs.**

Before implementing:

- State assumptions explicitly. If uncertain, **ask** instead of guessing.
- If multiple interpretations fit, **present them**—do not pick silently.
- If a simpler approach exists, say so; push back when warranted.
- If something is unclear, **stop**, name what is confusing, and ask.

## 2. Simplicity first

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No extra “flexibility” or configurability unless requested.
- No error handling for scenarios that are not realistically reachable.
- If the solution could be much shorter without losing clarity, simplify.

Test: “Would a senior engineer call this overcomplicated?” If yes, simplify.

## 3. Surgical changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Do not “improve” adjacent code, comments, or formatting unless required for the task.
- Do not refactor unrelated areas that are not broken.
- Match existing style even if you would do it differently.
- If you notice unrelated dead code, **mention it**—do not delete it unless asked.

When **your** changes create orphans:

- Remove imports, variables, or functions that **your** edits made unused.
- Do not remove pre-existing dead code unless the user asks.

Test: **Every changed line should trace directly to the user’s request.**

## 4. Goal-driven execution

**Define success criteria. Loop until verified.**

Reframe work as checkable outcomes:

| Instead of | Prefer |
|------------|--------|
| “Add validation” | Tests for invalid inputs, then make them pass |
| “Fix the bug” | A test that reproduces the bug, then make it pass |
| “Refactor X” | Tests pass before and after |

For multi-step work, outline a short plan with verification per step:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong criteria support independent iteration; vague “make it work” invites rework.

## Signs this is working

- Diffs mostly contain requested changes.
- Fewer rewrites from overcomplicated first drafts.
- Clarifying questions happen **before** implementation, not only after mistakes.

## Source

Upstream text and install options: [https://github.com/forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills).
