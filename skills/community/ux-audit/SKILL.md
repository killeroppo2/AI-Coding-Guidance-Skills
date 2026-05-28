---
name: ux-audit
description: "UX audit skill that simulates real user behavior to find usability problems. Triggers on: /ux-audit, 审计 UX, UX review, 检查体验, 这个页面有啥问题, audit UX, check experience."
---

# UX Audit

## What This Skill Does

Performs a structured usability review by simulating real user behavior across 5 dimensions. Produces a prioritized report of usability problems with concrete, implementable fixes.

**Who this is for:** AI creators who want to find UX problems before real users hit them.

**How to use it:** Type `/ux-audit [path]`. The AI audits the specified files and outputs a severity-ranked report. This skill reports problems only; use `/iterate` to fix them.

**Why structured audit:** A single "check my UX" prompt produces shallow feedback biased toward what the reviewer happens to notice. Structured auditing forces examination across 5 orthogonal dimensions with pass/fail criteria, eliminating blind spots (accessibility, edge cases, state feedback) that unstructured reviews consistently miss.

---

## When NOT to Use This

- **No UI exists:** Not useful for backend-only services or CLI tools without a terminal UI
- **No code yet:** Wireframes/mockups only - use design review instead
- **Known specific bug:** Fix it directly rather than running a full audit
- **Performance issue:** Use profiling tools; this skill checks usability, not speed

**Time:** Single page = 5-10 min. Full project (10+ UI files) = 20-40 min.

---

## Trigger

```
/ux-audit [file-or-folder]
```

| Command | Audits |
|---------|--------|
| `/ux-audit src/pages/Login.tsx` | Single file |
| `/ux-audit ui/` | All files in directory |
| `/ux-audit .` | All UI files in project |

**Alternative triggers:**

| Phrase | Meaning |
|--------|---------|
| 审计 UX (shen ji UX) | "audit the UX" |
| 检查体验 (jian cha ti yan) | "check the experience" |
| 这个页面有啥问题 (zhe ge ye mian you sha wen ti) | "what's wrong with this page?" |
| UX review / audit UX / check experience | English equivalents |

**Scope rule:** If no path specified, audit all UI files (components, pages, layouts, styles). If the specified path does not exist, report the error and list available UI directories.

---

## Role

Senior UX QA engineer simulating real user behavior through static code analysis.

**IS:** Find problems that cause users to fail, abandon, or feel confused.
**IS NOT:** Code review, linting, syntax checking, or performance profiling.

If the target path contains non-UI files (utilities, configs, tests), skip them silently. Only audit files that render user-facing interface.

**Simulated users:**

| User Type | What breaks for them |
|-----------|---------------------|
| Non-technical | Hidden actions, jargon, unclear next steps |
| Impatient (2s tolerance) | Missing loading states, no progress indicators |
| Distracted (returns later) | Lost state, no save, unclear resume point |
| First-time (zero context) | Missing onboarding, confusing navigation |
| Mobile (one thumb, 375px) | Small targets, horizontal scroll, hidden elements |
| Offline/slow network | No offline handling, lost data, infinite spinners |

---

## 5 Audit Dimensions

Apply ALL 5 dimensions to every target file. Do not skip any dimension. For each check, produce PASS or FAIL. If FAIL, record the severity and location.

### 1. Happy Path Flow

| # | Check | How to verify (static analysis) | FAIL = |
|---|-------|--------------------------------|--------|
| 1 | Main action completed without hesitation | Trace primary CTA (Call to Action) to completion handler | Critical failure |
| 2 | No unnecessary steps | Count steps from entry to completion | Friction |
| 3 | Next action always obvious | Check each view for a visible primary CTA | Navigation failure |
| 4 | UI responds within 300ms | Look for async calls without loading states, setTimeout > 300, synchronous blocking calls | Perceived broken |
| 5 | Primary CTA visible without scrolling | Check if CTA is above fold in layout | Conversion failure |
| 6 | Can go back/undo at every step | Check for back navigation and undo handlers | Trapped state |

### 2. Blind User Intuition

Test whether a user with zero context can navigate by UI labels alone.

| # | Element | Pass Criteria | How to verify |
|---|---------|--------------|---------------|
| 1 | Buttons | Label uses verb + noun ("Save Draft", "Delete Account") | Read all button text |
| 2 | Inputs | Placeholder or label shows valid format example | Check placeholder/label attributes |
| 3 | Empty states | Show a specific next action, not just "No items" | Find empty-state components |
| 4 | Forms | Required fields marked, constraints visible before submit | Check form validation logic |
| 5 | First use | Clear starting point visible within 3 seconds | Check initial render for CTA |
| 6 | Affordances | Clickable elements have cursor:pointer and visual distinction | Check interactive element styles |

**Rule:** If a user must stop to think "what do I do next?", the UX has failed at that point.

### 3. Edge Cases & Fault Tolerance

Test what happens when users behave unexpectedly or conditions degrade.

| # | Scenario | Expected behavior | How to verify |
|---|----------|-------------------|---------------|
| 1 | Button clicked 5x rapidly | Only one action executes | Check for debounce/disable on click handlers |
| 2 | Form submitted while pending | Submission blocked or queued | Check submit button disabled state during async |
| 3 | Invalid input (special chars, 10k chars, empty) | Inline error shown, form state preserved | Check validation rules and error display |
| 4 | Network drops during async operation | Error message + retry option shown | Check error handling in fetch/axios calls |
| 5 | User leaves mid-operation, returns | State preserved or user informed of loss | Check for state persistence (localStorage, draft save) |
| 6 | API returns null/undefined for expected data | Fallback text shown, no crash | Check data rendering for null guards |
| 7 | Mobile keyboard covers input | Active input scrolls into view | Check for scroll-into-view on focus |
| 8 | Two tabs open, concurrent actions | No data corruption | Check for optimistic update conflicts |

### 4. State Feedback

Verify that every user action produces visible acknowledgment.

| # | State | Required feedback | How to verify |
|---|-------|-------------------|---------------|
| 1 | Loading | Spinner or skeleton shown within 300ms | Check async calls for paired loading state |
| 2 | Button pressed | Immediate visual change (disabled state, icon swap) | Check onClick handlers for state updates |
| 3 | Success | Toast, confirmation message, or navigation to next step | Check success path in handlers |
| 4 | Failure | Message stating: what failed, why, what to do next | Check catch/error blocks for user-facing messages |
| 5 | Timeout (10s+) | "Taking longer than expected. [Retry] [Cancel]" | Check for timeout handling on long operations |
| 6 | Background work | Non-blocking progress indicator | Check async operations for progress reporting |

**Rule:** The user must NEVER wonder "Did my action work?" If any action lacks feedback, mark FAIL.

### 5. Information Hierarchy

Verify visual structure guides the eye to what matters most.

| # | Element | Pass Criteria | How to verify |
|---|---------|--------------|---------------|
| 1 | Primary CTA | Visually dominant: largest size, highest contrast | Compare CTA size/color to surrounding elements |
| 2 | Spacing | Consistent 8px grid throughout | Check margin/padding values for 8px multiples |
| 3 | Typography | Clear size/weight hierarchy (H1 > H2 > body) | Check font-size and font-weight declarations |
| 4 | Visual noise | Max 3 attention-competing elements per screen | Count bold/colored/animated elements per view |
| 5 | Responsive | No overlap or hidden elements at 375px width | Check for overflow:hidden, fixed widths > 375px |
| 6 | Contrast | 4.5:1 for body text, 3:1 for large text per WCAG (Web Content Accessibility Guidelines) AA | Calculate contrast ratio from color values |

---

## Output Format

Produce the following markdown structure. Every field must be filled; use "None" if a section has no items.

```markdown
# UX Audit Report: [path]

## Scope
- Files audited: [count] | Dimensions applied: All 5 | Personas that revealed issues: [list names]

## HIGH Priority (user fails or loses data)
### [Issue Title]
- **Dimension:** [1-5 name] | **Location:** file:line
- **Problem:** [one sentence describing what breaks]
- **User impact:** [one sentence describing what the user experiences]
- **Fix:** [concrete change with code snippet]

## MEDIUM Priority (confusion or friction)
| # | Issue | Dimension | Location | Fix |
|---|-------|-----------|----------|-----|

## LOW Priority (polish)
| # | Observation | Suggestion |
|---|-------------|-----------|

## Summary
- HIGH: [n] MEDIUM: [n] LOW: [n]
- Health: CRITICAL (any HIGH) | POOR (3+ MEDIUM) | FAIR (1-2 MEDIUM) | GOOD (LOW only or none)
```

---

## Severity Rules

- **HIGH:** User cannot complete their task, or loses data. Must fix before release.
- **MEDIUM:** User completes task but with confusion or friction. Fix this sprint.
- **LOW:** Polish opportunity with no functional impact. Add to backlog.

---

## Behavioral Rules

**MUST:**
- Simulate all 6 user types for every target
- Provide implementable code for every HIGH fix
- Include file:line for every finding
- Evaluate at 375px viewport width
- Check all async operations for feedback states

**MUST NOT:**
- Praise without evidence of quality
- Give generic advice ("consider improving...")
- Focus on syntax or lint issues (use linters for that)
- Skip any of the 5 dimensions
- Downgrade severity to avoid confrontation

**Edge cases:**
- If audit finds zero issues across all 5 dimensions: re-run Dimension 3 (Edge Cases) with the Malicious user persona. If still zero, report "No issues found" with confidence level.
- If target path contains no UI files: report "No auditable UI files found in [path]" and suggest correct path or scope.
- If project has no CSS/styles (server-rendered plain HTML): skip Dimension 5 visual checks, note in report as "Not applicable: no styling layer."

---

## Customization & Integration

**You can change:**
- Scope: audit a single file, directory, or entire project
- Focus: audit a single dimension with `--dimension N` (e.g., `/ux-audit path --dimension 3`)
- Personas: add rows to the simulated users table
- Checklists: add rows to any dimension table for domain-specific concerns
- Severity thresholds: adjust what counts as HIGH vs MEDIUM for your context

**Must stay fixed:**
- 5-dimension structure (unless explicitly scoped to one dimension)
- Output format structure (enables machine parsing and CI integration)
- Concrete implementable fixes for every HIGH issue
- PASS/FAIL evaluation for every check

**Composability:**
- Run single dimension: `/ux-audit path --dimension 3` for edge cases only
- Chain with iteration: `/ux-audit` produces diagnosis, then `/iterate` applies treatment
- CI integration: output maps directly to GitHub Issues (HIGH), PR comments (file:line), and backlog items (MEDIUM)

---

## Examples

```
"/ux-audit src/pages/Login.tsx" -> Audit Login, all 5 dimensions
"审计 UX" -> "Audit the UX" -> All UI files
"这个页面有啥问题" -> "What's wrong with this page?" -> Current page
"Check the UX of my checkout flow" -> Find checkout files, all 5 dimensions
```
