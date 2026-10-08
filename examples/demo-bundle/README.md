# Static synthetic demo bundle (M30 DEMO-1)

A committed, offline artifact so an evaluator can see agentwatch's value **before** wiring any hooks. It opens
from the local filesystem with **zero network requests, no server, no telemetry, and no account**.

- `bundle.json` — one synthetic session's **replay** timeline, **impact** facts, **oversight** authorization mix
  and human prompts, and **provenance** (retained-change) — plus the three verdicts (intact / complete / leak-free).

The data is **synthetic** (`session.producer.kind: demo`, `synthetic: true`) and is **never evidence**. It carries
no URL, no host that resolves, and no secret; `packages/python-sdk/tests/test_demo_bundle.py` asserts it opens
offline with zero network references and is clean under two independent secret scanners (the product scanner
`agentwatch.secrets.detect` and the pinned gitleaks/detect-secrets oracle).

## Open it

Open this bundle in the offline evidence verifier page (**30.VFY-1**, PRD 57):

```
open examples/demo-bundle/bundle.json   # in the VFY-1 page, from file://
```

The browser rendering is owned by **30.VFY-1** and is **deferred** in this branch (the page is not present here);
the artifact is complete and the page consumes it unchanged when it lands.

## Regenerate

The bundle is static and hand-authored synthetic content; it has no generator and makes no capture. If a field is
added, update `bundle.json` and the assertions in `tests/test_demo_bundle.py` together.
