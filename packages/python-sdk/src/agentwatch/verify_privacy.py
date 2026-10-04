"""``agentwatch verify-privacy``: prove the redaction story (M5 G1, #188).

Runs the self-test corpus through the *current* config and scans the *current*
store for any surviving secret marker. The verdict never echoes a leaked value
(it reports locations/kinds), so the output is safe to share.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from agentwatch.redact import RedactionConfig
from agentwatch.secrets import redact_secrets
from agentwatch.selftest import run_redaction_self_test
from agentwatch.store import RecordStore


@dataclass(frozen=True)
class PrivacyVerdict:
    """The result of a privacy verification pass."""

    passed: bool
    checks: int
    leaks: tuple[str, ...] = field(default_factory=tuple)
    quarantine_present: bool = False


def verify_privacy(store_path: Path | str, *, cfg: RedactionConfig | None = None) -> PrivacyVerdict:
    """Verify the redaction pipeline and scan the store for leaks."""
    path = Path(store_path)
    self_test = run_redaction_self_test(cfg)
    leaks: list[str] = list(self_test.leaks)

    store = RecordStore(path)
    records = store.records()
    for record in records:
        text = json.dumps(record.to_dict())
        _, kinds = redact_secrets(text)
        if kinds:
            # Report the location and kinds, never the value.
            leaks.append(f"store session={record.session_id} kinds={','.join(kinds)}")

    quarantine = path.parent / "quarantine.jsonl"
    return PrivacyVerdict(
        passed=not leaks,
        checks=self_test.checked + len(records),
        leaks=tuple(leaks),
        quarantine_present=quarantine.exists() and quarantine.stat().st_size > 0,
    )
