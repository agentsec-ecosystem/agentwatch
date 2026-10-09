# Detector Numbers — v0.2.0 (32.19)

**BLUF:** Detector precision/recall are **published against a versioned public corpus**, the field-test matrix
reports **40/40 rule detectors non-silent (100%)** (≥80% gate), and the **claims ledger is green**.

## Published numbers

- **Catalog:** [`docs/reference/detector-catalog.md`](../../reference/detector-catalog.md) — generated from the
  **147-scenario** field-test rule matrix (corpus `detector-corpus v1`), offline. Regenerate with
  `python3 scripts/generate_detector_catalog.py`; drift is guarded by
  `services/analytics/tests/test_detector_catalog.py` (the committed doc cannot diverge from the matrix).
- **Non-silent:** **40/40 rule detectors (100%)** — the matrix gate requires **≥80%** of rule detectors to fire on
  ≥1 positive (`services/analytics/tests/test_detector_non_silent.py`; field case FT-DET-2 `--nonsilent-80`).
- **Determinism:** the offline eval harness reproduces byte-for-byte (`test_detector_eval.py`; FT-DET-1).
- **Second corpus:** numbers reproduce on a corpus other than the tuning corpus (`test_detector_corpus.py`;
  FT-COR-1).
- **LLM detectors:** the LLM-augmented detectors run on the same offline harness, additive, never in the
  deterministic trust path (`test_llm_eval.py`; FT-DET-3).
- **Real traces:** every rule detector runs over the real licensed captures (`test_detector_real_traces.py`;
  FT-DET-7).

## Claims ledger (green)

```sh
python3 scripts/check_claims.py
# claims ledger OK: 105 claims, 417 live evidence links
```

Every public claim traces to live evidence (`test:`/`file:`/`script:`/`workflow:`/`doc:`); a renamed test or
deleted file fails the check. The published table (`docs/release/claims-ledger.md`) is generated from the ledger
(`--write`) and cannot drift. Field case FT-CLAIM-1 is green.

## Reproduction

```sh
python3 scripts/generate_detector_catalog.py     # regenerate the catalog
python3 scripts/check_claims.py                  # verify the ledger
make test                                        # runs the detector + catalog + ledger gates
```
