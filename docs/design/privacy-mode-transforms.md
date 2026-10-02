# Design — Privacy-Mode Transforms (detail)

**BLUF:** Exact transforms per mode, complementing [redaction-rules.md](redaction-rules.md) and
[privacy-data-handling.md](privacy-data-handling.md).

| Mode | Transform | Example (input `{"token": "sk-abc123", "q": "hello"})` |
|---|---|---|
| metadata-only | keep keys; drop values | `{"token": "<omitted>", "q": "<omitted>"}` |
| truncated | value[:N] + hash suffix | `{"token": "<REDACTED:api-key>", "q": "hel…#a1b2"}` |
| hashed | `sha256(value)[:16]` | `{"token": "<REDACTED:api-key>", "q": "8b2f…"}` |
| full | raw (but secret classes still redacted) | `{"token": "<REDACTED:api-key>", "q": "hello"}` |

Secret/PII classes are **always** redacted regardless of mode (see redaction-rules). Truncation N=32
(configurable). Hash = `sha256` (configurable). Records carry the `privacy_mode` used.
