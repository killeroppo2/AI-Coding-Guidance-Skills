---
name: relentless-iteration
description: "Multi-round critical iteration combining code hardening AND real-user UX stress-testing. Triggers on: /iterate, 迭代, 挑刺, 优化循环, iterate, polish, keep improving, harden this, stress test, find problems, iterate until done."
---

# Relentless Iteration

## What This Skill Does

Runs repeated rounds of critical analysis on your code and UI. Each round, the AI adopts a different user persona, executes your system's flows, finds real problems, implements fixes, and verifies with tests. Repeats until the system meets all stopping criteria.

**Who this is for:** AI creators who want automated stress-testing from multiple real-world perspectives.

**How to use it:** Type `/iterate`. The AI begins multi-round improvement immediately with no further input needed.

**Why this approach:** Ad-hoc prompting ("review my code") produces shallow single-perspective feedback. Structured iteration with 12 rotating personas and a 5-dimension checklist catches 3-5x more issues by eliminating perspective blind spots. Without structure, teams find the same surface issues repeatedly while deep problems ship to production.

---

## When NOT to Use This

- **No code yet:** Use brainstorming/design skills for greenfield ideation
- **Single known bug:** Just fix it directly
- **Documentation-only:** Use writing/editing skills
- **Performance profiling:** Use dedicated profiling tools
- **Backend with no UI:** Pass `backend` scope to skip UX checks

**Time:** 10 rounds = 15-40 findings, 20-45 min. 20 rounds = 30-70 findings, 40-90 min.

---

## Fast Mode (效率优先)

> 兵贵神速 — Speed is the essence of war.
> 少则得，多则惑 — Less yields gain; more yields confusion.

Fast mode optimizes for speed and cost while maintaining zero-HIGH guarantee. Use when:
- Iterating on a project you've already iterated before
- CI budget is limited
- Rapid feedback is more valuable than exhaustive coverage

**Differences from maximum mode:**

| Aspect | Maximum Mode | Fast Mode | Savings |
|--------|-------------|-----------|---------|
| Test strategy | Full suite every round | Related tests only; full suite on final round | ~70% test time |
| Checklist | All 20 items every round | Only items matching round focus (see table below) | ~50% analysis tokens |
| Stopping criteria | 6 conditions + 2 consecutive clean rounds | Min rounds + zero HIGH = done | 2 fewer rounds |
| Baseline | Full rebuild every time | Reuse `--status` output or prior iteration data | 5-10 min saved |
| Persona selection | Strict sequential rotation | Skip irrelevant personas for scope (see below) | ~30% fewer personas |

### Smart Test Strategy (智能测试)

Instead of running the full test suite every round:

1. **During each round:** Run only tests related to modified files:
   - `pytest tests/test_<module>.py -q` for each modified module
   - Or `pytest -k "keyword" -q` matching the fix area
2. **Final round only:** Run full test suite with coverage to confirm zero regressions
3. **If a related test fails:** Fix immediately before proceeding (same as maximum mode)

This follows 道德经 "大道至简" — test what you changed, not what you didn't.

### Focused Checklist (聚焦检查)

Instead of evaluating all 20 checklist items every round, match checklist to round focus:

| Round Range | Checklist Items to Evaluate |
|-------------|----------------------------|
| 1-2 (Surface) | Engineering #1, #3, #4 only |
| 3-4 (Structural) | Engineering #2, #5 only |
| 5-6 (Usability) | UX dimensions 1-5 (skip if backend scope) |
| 7-8 (Operational) | Engineering #1, #4 + custom: timeout/concurrency/resource |
| 9-10 (Edge cases) | Engineering #4 + custom: injection/overflow/adversarial |

Items not in the current round's focus are assumed PASS unless a finding surfaces naturally during flow execution.

### Persona Skip Rules (画像跳过)

Skip personas whose primary concern doesn't apply to the current scope:

| Scope | Skip Personas | Reason |
|-------|--------------|--------|
| `backend` | #2 (commuter), #4 (elder), #6 (screen reader), #8 (designer) | No UI to test |
| `infra` | #2, #3, #4, #5, #6, #7, #8, #9, #10 | Only #1 (first-time), #11 (malicious), #12 (DevOps) apply |
| `ui` | #11 (malicious), #12 (DevOps) | Security and ops are backend concerns |

When a persona is skipped, advance to the next applicable persona. Round number still increments.

### Relaxed Stopping Criteria

In fast mode, stop when ALL of:
1. Minimum requested rounds completed.
2. Zero HIGH findings in the latest round.
3. Coverage >= target (checked only on final round).

Do NOT require:
- Two consecutive clean rounds (one clean round is sufficient in fast mode)
- Simulated new user walkthrough (replaced by docs spot-check)
- Feature completeness audit (deferred to maximum mode)

### Cost Estimate

| Rounds | Maximum Mode | Fast Mode | Savings |
|--------|-------------|-----------|---------|
| 5 | ~100K tokens, 15-30 min | ~40K tokens, 8-15 min | 60% |
| 10 | ~200K tokens, 30-60 min | ~80K tokens, 15-30 min | 60% |
| 20 | ~400K tokens, 60-90 min | ~160K tokens, 30-50 min | 60% |

---

## Trigger

```
/iterate [rounds] [scope] [strictness]
```

| Command | Rounds | Scope | Strictness |
|---------|--------|-------|------------|
| `/iterate` | 10 | full-stack | maximum |
| `/iterate 20` | 20 | full-stack | maximum |
| `/iterate ui` | 10 | UI/UX only | maximum |
| `/iterate backend` | 10 | Backend only | maximum |
| `/iterate mild` | 10 | full-stack | reduced (critical only) |
| `/iterate 5 ui` | 5 | UI/UX only | maximum |
| `/iterate fast` | 10 | full-stack | efficiency (fast mode) |
| `/iterate fast backend` | 10 | Backend only | efficiency |

**Alternative triggers:**

| Phrase | Meaning |
|--------|---------|
| 迭代 (die dai) | "iterate" |
| 挑刺 (tiao ci) | "find faults/nitpick" - max strictness |
| 优化循环 (you hua xun huan) | "optimization loop" |
| polish / keep improving | refine quality |
| harden this | robustness focus (backend) |
| stress test / find problems | find breaking points |
| fast / 快速迭代 (kuai su die dai) | efficiency mode - 2x speed, -60% cost |

**Parameters:**

| Parameter | Default | Values |
|-----------|---------|--------|
| Rounds | 10 | 1-100 |
| Scope | full-stack | `full-stack`, `ui`, `backend`, `frontend`, `infra` |
| Strictness | maximum | `maximum`, `fast` (efficiency mode), `mild` (critical/high only) |

---

## Process

### Step 1: Establish Baseline (once before Round 1)

1. Run full test suite. Record in output: total tests, passes, fails, coverage %.
2. If no test runner exists: note "No test runner found" and skip coverage tracking. Use manual verification (run app, confirm no errors) as the regression check.
3. If tests fail on first run: fix failing tests as Round 0, commit `fix(tests): baseline repair`, then proceed.
4. Read entry points: config files, app entry, route definitions, primary modules.
5. List claimed capabilities from README/docs as a numbered checklist.
6. Map user flows: produce a numbered list of every action sequence from first visit to task completion.

**Scope definitions:**

| Scope | Files included |
|-------|---------------|
| `full-stack` | All source files: frontend, backend, config, tests |
| `ui` | Components, pages, layouts, styles, templates (*.tsx, *.vue, *.html, *.css) |
| `frontend` | Same as `ui` plus client-side logic, state management, API calls |
| `backend` | Server code, APIs, database, middleware, jobs (skip all UI checks) |
| `infra` | Dockerfiles, CI configs, deploy scripts, env files |

### Step 2: Execute Rounds (repeat 1 through N)

#### 2a. Select Persona

Rotate sequentially through the table below. After Persona 12, restart from Persona 1 (Round 13 uses Persona 1 again, Round 14 uses Persona 2, etc.).

| # | Persona | Primary task to attempt |
|---|---------|------------------------|
| 1 | First-time user | Complete onboarding with zero prior knowledge |
| 2 | Busy commuter (phone) | Finish core task one-handed, 375px, under 5 taps |
| 3 | Heavy data user | Search, filter, batch operate on 100+ items |
| 4 | Elder (65+) | Complete task with large fonts, high contrast, simple flows |
| 5 | Non-native speaker | Navigate with mixed-language input, no jargon |
| 6 | Screen reader user | Complete task keyboard-only with ARIA (Accessible Rich Internet Applications) labels |
| 7 | Impatient (2s attention) | Get result or abandon if no instant feedback |
| 8 | Perfectionist designer | Verify pixel alignment, 8px grid, visual consistency |
| 9 | Minimalist | Remove anything not required for core function |
| 10 | Competitor's user | Compare feature parity, find unique advantages |
| 11 | Malicious user | Attempt XSS, injection, oversized input, rapid-fire requests |
| 12 | DevOps (3 AM incident) | Kill services, corrupt data, simulate network partitions |

#### 2b. Execute the Flow

For the selected persona, perform these steps in order:

1. Open the application entry point.
2. Attempt the persona's primary task (defined in persona table above).
3. Produce a numbered list of observations: every confusion, error, delay, missing feedback, or broken flow encountered.
4. For each observation, record: file path, line number, and what went wrong.

If persona cannot complete their task, mark it as an automatic HIGH finding.
If persona completes the task with no issues, proceed to Step 2c (the checklist may still reveal problems).

#### 2c. Criticize (Checklist)

Evaluate each item. Produce PASS or FAIL for every row. If FAIL, record the severity shown.

**Engineering:**

| # | Question | If FAIL |
|---|----------|---------|
| 1 | Breaks under 100 concurrent users? | High |
| 2 | Dead code (defined, never called)? | Medium |
| 3 | Docs claim unimplemented feature? | High |
| 4 | Malformed input / timeout / null handling? | High |
| 5 | Hardcoded values / assumed environment? | Medium |

**UX (5 dimensions from /ux-audit):** Skip if scope is `backend` or `infra`.

| # | Dimension | Pass Criteria |
|---|-----------|--------------|
| 1 | Happy Path Flow | Primary task completes in under 3 clicks with no hesitation |
| 2 | Blind User Intuition | Every element understandable without reading docs |
| 3 | Edge Cases & Fault Tolerance | Rapid clicks, race conditions, offline: all handled gracefully |
| 4 | State Feedback | Visible feedback appears within 300ms of user action |
| 5 | Information Hierarchy | Most important element is visually dominant on screen |

**Measurable standards:**

| Check | How to verify | Pass |
|-------|---------------|------|
| Content findable in under 3s | Count navigation steps to reach content | Yes/No |
| Core task done without instructions | Attempt task using only UI labels | Yes/No |
| Errors show what/why/next-step | Trigger an error, check message content | Yes/No |
| Ops >300ms show progress | Find async calls, check for loading states | Yes/No |
| Empty states show guidance | Check components when data list is empty | Yes/No |
| Touch targets >= 44x44px | Check CSS width/height or padding on interactive elements | Yes/No |
| Contrast >= 4.5:1 body, 3:1 large | Check color values against WCAG AA standard | Yes/No |
| No overflow at 375px | Check CSS for fixed widths > 375px, missing responsive rules | Yes/No |
| Zero jargon, verb-first labels | Read all button/link text for plain language | Yes/No |
| Destructive actions need confirm+undo | Find delete/remove actions, check for confirmation dialog | Yes/No |

Output per problem: `[HIGH/MEDIUM/LOW]` + file:line + description + impact on users.

**Severity definitions:**
- **HIGH:** User cannot complete their task, or loses data. Must fix before release.
- **MEDIUM:** User completes task but with confusion or friction. Fix this sprint.
- **LOW:** Polish opportunity with no functional impact. Add to backlog.

#### 2d. Propose Fixes

For each problem found, produce:
1. What is wrong (1 sentence).
2. Why it matters to users (1 sentence).
3. Exact fix: specific code change, implementable without further research.

If no problems found in both 2b and 2c: select the most adversarial persona from the table (Persona 11: Malicious user) and re-run Step 2b with that persona. If still zero findings, record "Clean round" and proceed.

#### 2e. Implement & Verify

1. Modify code to apply each fix.
2. Add or update tests for each change.
3. Run full test suite. (In fast mode: run only related tests; full suite on final round only.)
4. Confirm: test count >= baseline, no new failures, no regressions.
5. Re-check each fix: does the fix introduce any new problem? If yes, fix that too.
6. Commit: `fix(scope): description (Round N)`

Do NOT proceed to next round if verification fails. Fix first.

**Guardrails:**
- Only fix problems that have a clear negative user impact. Do not optimize preemptively.
- If the same file is modified 3+ times in one round, stop and reassess whether the approach is correct before continuing.
- When two personas give conflicting recommendations (e.g., Persona 7 wants speed, Persona 4 wants simplicity), prefer the fix that serves the broadest user base.
- If a fix introduces a new problem that itself requires a fix, and that second fix also introduces a problem, stop the chain. Revert to the pre-fix state and choose a different approach.

### Step 3: Escalation (Focus Progression)

Each round range shifts focus to deeper concerns. Earlier rounds fix surface issues; later rounds dig into structural and adversarial problems.

| Rounds | Focus area | Example findings |
|--------|------------|------------------|
| 1-2 | Surface: error handling, broken links, obvious gaps | Missing 404 page, unhandled null |
| 3-4 | Structural: architecture, dead code, missing tests | Unused imports, untested branch |
| 5-6 | Usability: first-run experience, docs, accessibility | No onboarding, missing alt text |
| 7-8 | Operational: concurrency, performance, degradation | Race condition, no timeout |
| 9-10 | Edge cases: adversarial input, integration, polish | XSS vector, inconsistent spacing |
| 11+ | Apply stopping criteria (see Step 4) | If criteria unmet, continue |

### Step 4: Stopping Criteria

Stop when ALL of the following are true simultaneously:
1. Minimum requested rounds completed.
2. Coverage >= target (default 90% for apps with existing tests; skip if no test runner).
3. Latest round produced zero HIGH or MEDIUM issues.
4. A simulated new user can complete the primary task from docs alone.
5. Every feature claimed in README/docs is implemented and tested.
6. Two consecutive rounds produced zero substantial findings (confirms genuine completion, not oversight).

If ANY condition is false: continue to next round.
If total rounds executed > 2x originally requested: stop and report remaining issues as "deferred" in the final summary.

**Coverage target context:** 90% is the default for web applications and APIs with testable logic. Reduce to 70% for: infrastructure code, generated code, or legacy projects with no existing tests. State the chosen target and rationale in Round 1 output.

---

## Before/After Example

**Before (Round 3 input):**
```tsx
// LoginForm.tsx - no loading, no error handling
const handleSubmit = () => {
  fetch('/api/login', { method: 'POST', body: JSON.stringify(form) })
    .then(res => res.json())
    .then(data => setUser(data))
}
```

**Round 3 findings (Persona: Heavy data user):**
1. [HIGH] LoginForm.tsx:4 - No loading state. User clicks multiple times.
2. [HIGH] LoginForm.tsx:4 - No error handling. Network failure shows nothing.
3. [MEDIUM] LoginForm.tsx:4 - No validation before submit.

**After (Round 3 output):**
```tsx
const handleSubmit = async () => {
  if (!form.email || !form.password) return setError('Email and password required')
  setLoading(true); setError(null)
  try {
    const res = await fetch('/api/login', { method: 'POST', body: JSON.stringify(form) })
    if (!res.ok) throw new Error(`Login failed: ${res.statusText}`)
    setUser(await res.json())
  } catch (e) {
    setError(e.message + '. Check connection and retry.')
  } finally { setLoading(false) }
}
```

One round, one persona, 3 findings fixed. Multiply by 10 rounds across 12 personas.

---

## Output Format

### Per-Round

```markdown
## Round N: [Persona Name]

### Findings
1. [HIGH/MEDIUM/LOW] Problem (file:line)
   - Impact: what happens to users

### Fixes Applied
- file:line - what changed and why

### Verification
- Tests: X passed, Z added | Coverage: N% (or "N/A") | Commit: `fix(scope): msg (Round N)`
```

### Final Summary

```markdown
## Iteration Complete
- Rounds: N | Found: X (H:a M:b L:c) | Fixed: Y | Tests added: Z
- Coverage: before% -> after% (or "N/A: no test runner")

| Metric | Before | After |
|--------|--------|-------|
| Tests | ... | +N |
| Coverage | ... | +N% |
| Known issues | ... | -N |

### Remaining: [severity] description - reason unfixed
### Next Steps: 1. ... 2. ...
```

---

## Philosophy

Each principle connects to a concrete rule:

| Principle | Chinese | Rule |
|-----------|---------|------|
| Simplicity is sophistication | 大道至简 (da dao zhi jian) | Every fix reduces code lines OR user steps |
| Serve without competing | 水利万物而不争 (shui li wan wu er bu zheng) | Remove UI that draws attention to tool over task |
| Less yields more | 少则得，多则惑 (shao ze de, duo ze huo) | If removing element doesn't break task, don't add it |
| Know yourself and enemy | 知己知彼 (zhi ji zhi bi) | Re-read code before each round, never assume |
| Speed is respect | 兵贵神速 (bing gui shen su) | Every operation: feedback within 300ms |
| Adapt to findings | 因敌变化而取胜 (yin di bian hua er qu sheng) | Shift focus based on what each round reveals |
| Efficiency is respect | 以逸待劳 (yi yi dai lao) | Don't spend 100% effort for 1% improvement |

---

## Anti-Patterns

| Don't | Do instead |
|-------|-----------|
| Add code without finding a problem | Problem first, then fix |
| Fix cosmetic issues while structural remain | HIGH before MEDIUM before LOW |
| Test the framework, not the system | Test real user actions |
| Stop early ("looks fine") | Complete minimum rounds |
| Sugarcoat ("could be improved") | "Broken because X. Fix: Y." |
| Add features disguised as fixes | Log feature requests separately |
| Analyze without changing code | Every round commits changes |
| Optimize code that works fine | Only fix clear negative user impact |
| Rewrite a file repeatedly in one round | 3+ edits to same file = reassess approach |

---

## Customization

**You can change:**
- **Rounds:** `/iterate N` (1-100)
- **Scope:** `ui`, `backend`, `frontend`, `infra`
- **Strictness:** `mild` for critical-only
- **Personas:** Add to pool table: `| # | Name | What they test |`
- **Checklists:** Add rows to any table for domain concerns
- **Stopping criteria:** Add conditions to the list
- **Quality targets:** Adjust coverage/thresholds

**Must stay fixed:**
- Round structure: persona -> walk -> criticize -> propose -> implement -> verify
- Zero regressions rule
- Severity classification (HIGH/MEDIUM/LOW)
- Verification step every round

**Composability:**
- Single focus: `/iterate ui` with UX checklist only
- Skill chaining: any skill's issue list feeds Round 1 input
- Single persona: "use persona 11 for all rounds" = security focus
- Pipeline: `/ux-audit` (diagnosis) then `/iterate` (treatment)

---

## CI/Workflow Integration

Structured output enables:
- **GitHub Issues:** HIGH findings = issues with severity label
- **PR comments:** file:line enables inline review comments
- **Sprint planning:** MEDIUM = backlog items
- **CI gate:** `/iterate 3 mild` as pre-merge quality check

---

## Examples

```
User: "/iterate" -> 10 rounds, full-stack, max strictness
User: "/iterate 20 ui" -> 20 rounds, UI only
User: "迭代这个页面，挑刺" -> "Iterate this page, nitpick" -> max strictness
User: "Keep iterating until production quality" -> stop when criteria met
User: "用挑刺者角度分析修复，不断循环" -> "Nitpick, fix, loop" -> full iteration
User: "/iterate fast" -> 10 rounds, full-stack, efficiency mode (smart tests, focused checklist)
User: "/iterate fast 5 backend" -> 5 rounds, backend only, efficiency mode
User: "快速迭代" -> fast mode, 10 rounds
```
