# Tutorial 10 — Cross-harness testing

How do you trust a harness adapter without the proprietary CLI? Replay golden
fixtures through the **shared conformance runner** (O1) and cross-check the file
formats against independent parsers.

## 1. The conformance runner (O1)

Every shipped adapter registers an `AdapterSpec` (fixtures dir, capabilities,
documented gaps) and must pass the same mechanical bar in CI: fixture replay,
capability/gap disjointness, explicit rejection of declared gaps and unknown
phases, and dedup idempotency.

```sh
pytest packages/python-sdk/tests/test_conformance_runner.py
# negative control: a deliberately broken adapter must FAIL the same checks
pytest packages/python-sdk/tests/test_conformance_runner.py::test_self_test_proves_a_broken_adapter_fails
```

## 2. Corpus layout

```
tests/testkit/<harness>/<version>/
  payloads/*.json        # hook payloads
  rollouts/*.jsonl(.zst) # rollout/log formats
  telemetry/*.log        # native OTel
  frames/*.json          # proxy frames
  manifest.json          # version tags, source citations, expected shape
```

## 3. Honest fidelity tiers

An adapter declares its tier — `live-verified | fixture-verified | modeled` — and
the compatibility matrix carries a **Protocol** column for the proxy. A modeled
adapter is never presented as captured; drift in a fixture shape is surfaced for
human review, never applied silently.

## 4. Cross-parser validation

For file formats, our reader is diffed against two independent OSS parsers on the
same fixtures (XHT-3). A divergence is a failing test or a documented
interpretation gap — and every parser is version-pinned and attributed in
`THIRD_PARTY_NOTICES`.

See [cross-harness-testing.md](../design/cross-harness-testing.md) and
[adapter-conformance.md](../reference/adapter-conformance.md).
