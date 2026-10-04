# Design — Threat → Control → Test Traceability

**BLUF:** Each threat in the [threat model](threat-model.md) maps to a control and a test that proves it.
No unverified controls.

| Threat | Control | Test |
|---|---|---|
| Spoofing (impersonate daemon) | Local socket perms; identity check | socket-perm test |
| Tampering (records edited) | Hash chain (DD-07) | `verify-store` + F4 fault test |
| Repudiation ("agent didn't do it") | Ordered, correlated records | replay-fidelity test |
| Info disclosure (secrets) | Redaction before store (DD-06); export gating (DD-09) | redaction attack pack; export-locked test |
| DoS (silent stop) | Fail-closed + health surfaced (NFR-8/12) | F1/F3 fault tests; `/healthz` |
| EoP (poisoned hook config) | Config validation; least privilege; signed releases | bad-config test (F7); supply-chain checklist |
| On-box tamper (kill/strip/move/skew) | Chain + recorder-state records + coverage reconciliation | anti-forensics suite; [recorder attack matrix](recorder-attack-matrix.md) |
