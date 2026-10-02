# Design — Redaction Rules

**BLUF:** What counts as a secret/PII, the four privacy modes, and the algorithms. This is what R7's attack
pack tests against.

Status: **shipped** (v0.1.0 M4).

## Implementation

`agentwatch.secrets` detects and masks the classes above as `<REDACTED:kind>` before any storage
transform, and `agentwatch.adapters.claude_code.normalize` attaches a `secret-detected` security event
(`emitter="agentwatch"`, `evidence={"kinds": [...]}`) when any fires — even in `metadata-only` mode.
Values under a sensitive key name (`*_TOKEN` / `*_KEY` / `*_SECRET` / `*_PASSWORD`) are masked wholesale
as `env-secret`. The fixed-corpus self-test lives in `agentwatch.selftest` (`run_redaction_self_test`,
`export_allowed`) and blocks export (DD-09).

## Privacy modes (applied per record at normalization, DD-06)

| Mode | Behavior | Default |
|---|---|---|
| `metadata-only` | record argument **shapes/keys** only; values omitted | ✅ |
| `truncated` | values truncated to N chars (default 32) with a hash suffix for correlation | |
| `hashed` | values replaced by `sha256(value)[:16]` (correlation without content) | |
| `full` | raw values (explicit opt-in; discouraged; warns) | |

## Secret/PII classes (detected even in `full` mode — never persisted)

| Class | Detection |
|---|---|
| API keys / tokens | known prefixes: `sk-`, `ghp_`, `gho_`, `github_pat_`, `AKIA…`, `xoxb-`, `AIza` |
| OAuth bearer | `Bearer …` |
| Private keys | `-----BEGIN … PRIVATE KEY-----` |
| JWTs | three base64 segments separated by `.` |
| Cloud secrets | AWS `AKIA` + 16 chars; GCP/Generic `ya29.`; Azure `Bearer` |
| PII (email/phone/SSN/credit-card) | regex (email, E.164, SSN, Luhn-checked cards) |
| Connection strings | `postgres://…`, `mongodb+srv://…`, `redis://…` with embedded creds |
| Environment vars by name | a denylist (`*_TOKEN`, `*_KEY`, `*_SECRET`, `*_PASSWORD`) |

## Algorithm

1. Parse arguments (JSON-shaped where possible; raw string otherwise).
2. Detect secret/PII classes → redact to `<REDACTED:kind>` even in `full` mode.
3. Apply the privacy mode to remaining values.
4. Emit a `secret-detected` security event when redaction fires (R5).
5. Persist; the redaction self-test (DD-09) runs before any export.

## Self-test

On startup and before export: run a fixed corpus of secret-bearing arguments through the pipeline and
assert none appear in the store. If any leaks, export stays blocked.

## Open questions

- Configurable denylist of env-var names per project (v0.1.x).
- Custom secret patterns (regex) — v0.2.0.
