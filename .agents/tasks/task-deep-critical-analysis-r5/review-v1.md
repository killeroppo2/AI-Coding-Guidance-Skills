# Kernel hardening: protocol docs, truncation, shutdown, skill factory, event detection, error UX

Six features added in a single batch: Mode 2 protocol documentation, skill content truncation for token budgets, graceful shutdown with signal handling, a skill factory for programmatic skill creation, external event detection for user-modified files, and user-friendly error messages. The batch tightens the kernel's operational boundaries — truncation prevents prompt blowouts, shutdown preserves state on Ctrl-C, and user-owned file protection prevents the evolution engine from clobbering manual edits.

**Watch for:** EventDetector is fully implemented and tested but never wired into the runner loop, so external changes are silently ignored at runtime (confirmed). The `validate_change` state parameter is only threaded through tests — no production caller passes state today (confirmed). The SIGINT handler doesn't terminate the AI subprocess, risking orphaned processes (confirmed).

## High-level view

The Mode 2 protocol documentation provides file format examples and a transition table for AI agents operating without the runner. The transition table could drift from `graph.yaml` since nothing enforces consistency between them.

Skill content truncation adds a two-stage strategy (summary mode, then hard-cut) to the context assembler, bounded by a per-skill character limit multiplied by the number of skills loaded. The hard-truncate fallback can split mid-code-fence or mid-YAML-block, producing malformed context that confuses downstream AI parsing.

Graceful shutdown registers SIGINT/SIGTERM handlers and an atexit hook in Mode 3, setting status to "interrupted" and persisting state. There's no subprocess cleanup: if the AI subprocess is mid-execution when the signal arrives, the child process is orphaned.

The skill factory encapsulates directory creation, SKILL.md generation, and index registration behind kebab-case validation, integrated into the evolution engine's `apply_change` for the `add_skill` type. No concurrent-write protection exists on the shared `_index.yaml` file.

EventDetector scans `kernel/prompts/`, `knowledge/rules/`, and `memory/` for files newer than `last_updated`. The implementation is entirely disconnected from the runner: nothing calls `detect_external_changes` in production. The user-owned file protection in `validate_change` requires a caller to pass the `state` dict — which no current production code path does.

Error messages provide a what/why/fix template system integrated at three points in the runner: stuck-node, timeout, and command-not-found. The `classify_error` function is tested but unused — the runner constructs error types explicitly rather than classifying raw error strings.

<details>
<summary>Issues (7)</summary>

1. **EventDetector dead code** — `detect_external_changes()` is never called from the runner or any production module. Wire it into the iteration loop or remove it to avoid maintenance burden.
2. **`validate_change` state param unused in production** — No caller passes `state` to `validate_change`, so user-owned file protection is inert. Thread state through `apply_change` and the feedback loop's evolution path.
3. **Subprocess orphan on signal** — The SIGINT/SIGTERM handler in Mode 3 calls `sys.exit(130)` without terminating the child subprocess. If the AI process is running, it becomes orphaned. Store the subprocess `Popen` handle and call `terminate()`/`kill()` in the handler.
4. **Hard truncation splits mid-content** — `_truncate_skill_content` slices at an arbitrary character boundary, potentially producing malformed YAML or broken markdown that the AI may misparse. Consider truncating at the last newline before the limit.
5. **`classify_error` unused** — The function exists and is tested but never called in production. The runner uses explicit error types at each call site. Either use classification (e.g., for raw stderr from AI subprocess) or remove it.
6. **`_index.yaml` concurrent write risk** — `SkillFactory.create_skill` does a read-modify-write on `_index.yaml` without any locking. Concurrent evolution proposals could corrupt the index.
7. **Transition table drift** — `state_transitions.md` documents transitions that could diverge from `graph.yaml` over time since no validation links them. Consider generating the doc from graph.yaml or adding a test.

</details>

<details>
<summary>Details</summary>

## EventDetector: implemented but unwired

Nothing in `runner.py` or the feedback loop instantiates `EventDetector` or calls `detect_external_changes`. The feature exists purely in tests. Similarly, `validate_change` accepts an optional `state` parameter for user-owned file checking, but the only production call sites — in `apply_change` (line 140 of `engine.py`) and `apply_if_confident` — never pass it:

```python
# engine.py line 140 - self-call without state
valid, reason = self.validate_change(change)
```

The entire user-owned-file protection codepath is dead in production. For it to function, `apply_change` would need to accept and forward state, and the caller (feedback loop) would need to provide it.

## Subprocess lifecycle gap in graceful shutdown

The signal handler registered in Mode 3:

```python
def _shutdown_handler(signum, frame):
    state_mgr.state["status"] = "interrupted"
    state_mgr.state.setdefault("errors", []).append(
        "Execution interrupted by signal"
    )
    state_mgr.save_state()
    sys.exit(130)
```

This saves kernel state but does not address the subprocess spawned by `subprocess.run()`. Because `subprocess.run()` is a blocking call, the signal handler fires inside the parent process while the child (the AI CLI command) may still be running. On `sys.exit(130)`, Python's cleanup may or may not terminate the child depending on OS behavior and whether stdin/stdout pipes are closed.

A more robust pattern: store the `Popen` handle (switching from `subprocess.run` to `subprocess.Popen`) and explicitly call `proc.terminate()` followed by `proc.wait(timeout=5)` in the handler. The current implementation risks orphaned AI processes accumulating if the user sends repeated interrupts during long AI calls.

The atexit hook fires after `sys.exit(130)`, but since the signal handler already set status to "interrupted", it no-ops. This ordering dependency is fragile — future code that modifies status between the signal handler and exit could break the assumption.

## Truncation: hard-cut produces potentially malformed context

The fallback path in `_truncate_skill_content`:

```python
return content[:max_chars] + "\n...[TRUNCATED]"
```

This can split in the middle of a code fence, leaving an unclosed ``` that downstream AI models may interpret as part of the prompt structure rather than skill content. Find the last `\n` before `max_chars` and cut there to preserve line-level integrity.

The per-skill budget `max_total = self.max_skill_content_chars * len(skill_names)` scales linearly with skill count. With the default of 8000 chars and 10 skills loaded, the budget is 80K characters — approaching the 100K warning threshold. The warning is emitted to stderr but doesn't trigger corrective action (like reducing the budget or dropping lower-priority skills).

## `classify_error` — tested utility without a caller

The runner already knows the error type at each call site — it calls `format_error("timeout", ...)` directly because it caught a `TimeoutExpired`. The classification function would be useful for parsing opaque error strings from an external source, but that pattern doesn't exist today. It's dead code in production.

## Skill factory index write safety

`SkillFactory.create_skill` delegates index registration to `self.store.add_skill()`, which does a YAML load-append-dump cycle on `_index.yaml`. If two `apply_change("add_skill", ...)` calls execute concurrently, the second read could see a stale index and overwrite the first addition. Unlikely in the current single-threaded runner but a real risk if evolution is ever parallelized.

</details>

<details>
<summary>File map</summary>

| File | Change |
|------|--------|
| `kernel/BOOT.md` | Added Mode 2 protocol reference links |
| `kernel/context_assembler.py` | Added truncation logic, context size warning, `max_skill_content_chars` parameter |
| `kernel/contracts/mode2_protocol.md` | New: full Mode 2 protocol documentation with file formats and examples |
| `kernel/contracts/state_transitions.md` | New: transition table with pre/post-conditions |
| `kernel/error_messages.py` | New: what/why/fix error templates and `classify_error` |
| `kernel/event_detector.py` | New: mtime-based external change detection and user-owned file tracking |
| `kernel/evolution/engine.py` | Added `state` param to `validate_change`, `add_skill` handling via SkillFactory |
| `kernel/skill_factory.py` | New: kebab-case validated skill creation with index registration |
| `runner.py` | Signal/atexit handlers, `--resume` from interrupted, `format_error` integration |
| `tests/test_context_assembler_truncation.py` | New: truncation and size estimation tests |
| `tests/test_error_messages.py` | New: format_error and classify_error tests |
| `tests/test_event_detector.py` | New: event detection and user-owned file protection tests |
| `tests/test_graceful_shutdown.py` | New: signal handler, atexit, resume, timeout tests |
| `tests/test_mode2_protocol.py` | New: protocol doc structure validation tests |
| `tests/test_skill_factory.py` | New: skill creation, template, and evolution integration tests |

Full diff: `git diff ef25a44..HEAD`

</details>
