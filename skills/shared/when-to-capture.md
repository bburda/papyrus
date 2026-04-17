# When to capture a memory (judgment pattern)

**This is a subjective judgment pattern, not an atomic skill.** Agents consult it before invoking `papyrus-write`.

## The filter

LLM agents converge independently on reasonable technical defaults. Memory adds **zero value** for default-convergent picks — another fresh agent would arrive at the same answer.

Memory provides unique value for:

### ✓ Capture
- **Arbitrary decisions** — picked from equivalent alternatives (e.g. error code `0x16` among unused slots)
- **Historical gotchas** — past bugs, rejected approaches, specific incidents
- **Long-horizon context** — decisions accumulating over 20+ sessions
- **Project-specific conventions** — violate or specialize common defaults
- **Verified specific values** — concrete numbers, names, IDs used elsewhere

### ✗ Skip
- **Default-convergent picks** — any agent would pick the same (e.g. "max key length = 128 bytes" when range is 32-256)
- **Textbook patterns** — standard architectural solutions
- **Re-derivable facts** — current state of a function / module (read code instead)
- **Ecosystem conventions** — universal defaults (JSON snake_case, PEP 8 spacing)

## Rule of thumb

> Would another fresh agent with the same task land on the same answer?
> **Yes** → skip. **No** → capture.

## Examples

### Capture (arbitrary)
- `DEC_partial_write_error_code_0x16` — picked from free slots
- `DEC_logging_filter_api_exclusion_lists` — team chose over inclusion
- `PREF_filter_naming_with_underscore_suffix` — local convention

### Skip (default-convergent)
- "Use `std::rename` for atomic writes" — standard default
- "Max key length = 128 bytes (power of 2, midpoint of 32-256)" — any agent would pick the same
- "Retry transient I/O errors with backoff" — textbook

## Applies to which atomic skills

- `papyrus-write` — consult BEFORE invoking
- `papyrus-update-metadata` — consult when elevating confidence or scope
