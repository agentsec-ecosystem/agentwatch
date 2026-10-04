# Tutorial 04 — Write a Detector

**BLUF:** Extend the detector engine with a rule-based signal.

1. Subclass the detector interface; declare `id`, `category`, and thresholds.
2. Return a structured anomaly record: `severity`, `explanation`, `evidence`.
3. Add a corpus fixture and a unit test asserting fire/no-fire.
4. Register it; update the [detector catalog](../reference/detector-catalog.md).

Use trailing baselines, not fixed thresholds (`DD` in the shipped project; AgentWatch lesson).
