# ADR-0036 — Local console security model

- **Status:** accepted (2026-10-07, v0.2.0 M30 LUI-1)
- **Context:** `agentwatch ui` (PRD 54 §LUI-1, [design/local-console.md](../design/local-console.md)) opens a browser
  view of the local chain store in one command with no Docker. A browser-facing local server on a developer machine
  is exposed to two concrete threats: **DNS rebinding** (a malicious page resolves its own hostname to `127.0.0.1`
  and reaches the server) and **drive-by / cross-site requests** from any page the developer has open. It must never
  become a mutation surface or an egress path.
- **Decision:** the console enforces, and tests enumerate, this model:
  1. **Loopback bind only.** The server binds `127.0.0.1`; a non-loopback `--host` is coerced to `127.0.0.1` and
     the address is asserted by test. It is never reachable off-host.
  2. **Per-launch token.** Every route requires a token generated with `secrets.token_urlsafe` at launch, passed
     in the URL or an `X-Agentwatch-Token` header and compared with `hmac.compare_digest`. The token is not
     persisted and rotates each launch.
  3. **Host-header check.** Only loopback `Host` values (`127.0.0.1`, `::1`, `localhost`, port-stripped) are
     accepted; anything else is `403`. This is the DNS-rebinding defense.
  4. **Read-only.** There is **no mutation endpoint**; only `GET` routes exist and `POST`/`PUT`/`PATCH`/`DELETE`
     return `405`. Reads never write to the store (the session export is read-only NDJSON).
  5. **No egress.** The process serves loopback requests and reads the store; it makes no outbound network call
     (guarded by the repo-wide dependency egress audit; the sole self-request is the loopback `--check` smoke).
  6. **Honest rendering.** Chain gaps, tombstones, and parse errors are surfaced (`/api/health`, the gap banner),
     never hidden; UI numbers equal the CLI `--json` (parity test).
- **Consequences:** a safe, zero-config first-minute view; the same console can later point at a fleet/Postgres
  tier without weakening the local model (that tier reuses the P7/GOV role model, PRD 56). No new dependency.
- **Alternatives rejected:** binding `0.0.0.0` (exposes the store on the LAN); no token (any local page could read
  the store via DNS rebinding); a static file server (would serve raw chain files without gap/redaction context).
