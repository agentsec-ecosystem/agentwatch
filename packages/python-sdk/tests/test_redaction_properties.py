"""Property-based + differential redaction testing (PRD 38 §Q1, issue #218).

The fixed corpus in ``agentwatch.selftest`` measures *regression*: it cannot find
the secret shape nobody thought of. This module generates secret-shaped strings
(key prefixes, base64url bodies, JWT triplets, connection strings) and runs them
through the redaction pipeline under channel mutation (surrounding text, JSON
encoding, log wrappers, unicode confusables), asserting no plaintext core
survives.

It also diffs agentwatch's recall against the pinned oracle rule table
(``_secret_oracle``), derived from gitleaks/detect-secrets. A rule class the
oracle catches but agentwatch misses must be declared in ``EXPECTED_GAPS``;
otherwise the differential test fails, so a new miss cannot pass silently.

Mutation is *gated by the oracle*: if a mutation destroys the secret's shape
(e.g. a unicode confusable), the oracle no longer matches it and the sample is
excluded from recall math — exactly the PRD 38 edge case "a generated string that
is not actually a secret".
"""

from __future__ import annotations

import json
import re
import string

import pytest
from _secret_oracle import EXPECTED_GAPS, ORACLE_RULES, OracleRule
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import DataObject

from agentwatch.secrets import redact_secrets

_ALNUM = string.ascii_letters + string.digits
_B64URL = string.ascii_letters + string.digits + "_-"
_AWS_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


# ---------------------------------------------------------------------------
# Secret-shaped generators, one per oracle rule class
# ---------------------------------------------------------------------------


def _luhn_check_digit(payload: str) -> str:
    """Return the Luhn check digit that makes ``payload + digit`` valid."""
    total = 0
    for index, char in enumerate(reversed(payload)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def _luhn_number(body: str) -> str:
    return body + _luhn_check_digit(body)


def _prefixed(prefix: str, size: int) -> st.SearchStrategy[str]:
    """A fixed prefix followed by an exactly ``size``-character alnum body."""
    body = st.text(alphabet=_ALNUM, min_size=size, max_size=size)
    return body.map(lambda value: prefix + value)


_PRIVATE_KEY = st.text(alphabet=_ALNUM + "+/", min_size=20, max_size=60).map(
    lambda body: (
        "-----BEGIN RSA "
        + "PRIVATE KEY-----\n"
        + f"{body}\n"
        + "-----END RSA "
        + "PRIVATE KEY-----"
    )
)
_AWS_ACCESS = st.text(alphabet=_AWS_ALPHABET, min_size=16, max_size=16).map(
    lambda body: "AKIA" + body
)
_SLACK_BOT = st.tuples(
    st.text(alphabet=string.digits, min_size=10, max_size=12),
    st.text(alphabet=_ALNUM, min_size=10, max_size=24),
).map(lambda parts: f"xoxb-{parts[0]}-{parts[1]}")
_GOOGLE_API = st.text(alphabet=_ALNUM + "_-", min_size=35, max_size=35).map(
    lambda body: "AIza" + body
)
_GOOGLE_OAUTH = st.text(alphabet=_B64URL, min_size=10, max_size=40).map(lambda body: "ya29." + body)
_JWT = st.tuples(
    st.text(alphabet=_B64URL, min_size=8, max_size=24),
    st.text(alphabet=_B64URL, min_size=8, max_size=24),
    st.text(alphabet=_B64URL, min_size=8, max_size=24),
).map(lambda parts: f"eyJ{parts[0]}.{parts[1]}.{parts[2]}")
_CONNECTION = st.tuples(
    st.sampled_from(["postgres", "postgresql", "mongodb", "mongodb+srv", "redis", "mysql", "amqp"]),
    st.text(alphabet=_ALNUM, min_size=1, max_size=8),
    st.text(alphabet=_ALNUM, min_size=1, max_size=8),
    st.text(alphabet=_ALNUM + ".", min_size=1, max_size=12),
).map(lambda parts: f"{parts[0]}://{parts[1]}:{parts[2]}@{parts[3]}/db")
_CREDIT_CARD = st.text(alphabet=string.digits, min_size=15, max_size=15).map(_luhn_number)
_SSN = st.tuples(
    st.text(alphabet=string.digits, min_size=3, max_size=3),
    st.text(alphabet=string.digits, min_size=2, max_size=2),
    st.text(alphabet=string.digits, min_size=4, max_size=4),
).map(lambda parts: f"{parts[0]}-{parts[1]}-{parts[2]}")
_EMAIL = st.tuples(
    st.text(alphabet=_ALNUM + "._%+-", min_size=1, max_size=12),
    st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8),
    st.sampled_from(["com", "org", "net", "io", "dev"]),
).map(lambda parts: f"{parts[0]}@{parts[1]}.{parts[2]}")
_PHONE = st.tuples(
    st.sampled_from("123456789"),
    st.text(alphabet=string.digits, min_size=6, max_size=14),
).map(lambda parts: f"+{parts[0]}{parts[1]}")
_BEARER = st.text(alphabet=_ALNUM + "._-", min_size=8, max_size=40).map(
    lambda body: f"Bearer {body}"
)

_STRATEGIES: dict[str, st.SearchStrategy[str]] = {
    "gitleaks/private-key": _PRIVATE_KEY,
    "gitleaks/aws-access-token": _AWS_ACCESS,
    "gitleaks/github-pat": _prefixed("ghp_", 36),
    "gitleaks/github-oauth": _prefixed("gho_", 36),
    "gitleaks/github-app-token": _prefixed("ghs_", 36),
    "gitleaks/github-refresh-token": _prefixed("ghr_", 76),
    "gitleaks/slack-bot-token": _SLACK_BOT,
    "gitleaks/google-api-key": _GOOGLE_API,
    "detect-secrets/google-oauth-id": _GOOGLE_OAUTH,
    "detect-secrets/jwt": _JWT,
    "gitleaks/connection-string": _CONNECTION,
    "detect-secrets/credit-card": _CREDIT_CARD,
    "detect-secrets/us-ssn": _SSN,
    "detect-secrets/email": _EMAIL,
    "detect-secrets/phone": _PHONE,
    "detect-secrets/bearer": _BEARER,
}

_RULES_BY_ID: dict[str, OracleRule] = {rule.id: rule for rule in ORACLE_RULES}

# Channel mutations. The secret stays intact in modes 0-3; mode 4 replaces Latin
# letters with Cyrillic confusables, which usually destroys the ASCII shape and is
# therefore excluded by the oracle gate (a documented, intentional non-claim).
_NOISE = st.text(
    alphabet=st.sampled_from(list(" \t\n\r,;:{}[]\"'`\\/|<>()=+*&^%$#@!~" + string.ascii_letters)),
    min_size=0,
    max_size=16,
)
_CONFUSABLES = str.maketrans(
    {"a": "\u0430", "e": "\u0435", "o": "\u043e", "c": "\u0441", "p": "\u0440"}
)


def _mutate(secret: str, mode: int, noise: str) -> str:
    """Wrap ``secret`` in a channel-representative context."""
    if mode == 0:
        return f"{noise}{secret}{noise}"
    if mode == 1:
        return json.dumps({"cmd": secret, "note": noise})
    if mode == 2:
        return f"Authorization: {noise} {secret}"
    if mode == 3:
        return f"{noise}\n{secret}\n{noise}"
    return secret.translate(_CONFUSABLES)


def assert_no_plaintext(rule: OracleRule, payload: str) -> None:
    """Assert no oracle-matched secret span survives agentwatch redaction.

    A payload with no oracle match is not that secret class (mutation destroyed
    its shape) and is skipped rather than counted as a pass.
    """
    spans = [match.group() for match in rule.pattern.finditer(payload)]
    if not spans:
        return
    masked, _ = redact_secrets(payload)
    surviving = [span for span in spans if span in masked]
    assert not surviving, f"{rule.id}: plaintext survived redaction: {surviving!r}"


# ---------------------------------------------------------------------------
# Property: no plaintext survives channel mutation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule_id", sorted(_STRATEGIES))
@settings(
    max_examples=120,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
@given(data=st.data())
def test_no_plaintext_survives_channel_mutation(rule_id: str, data: DataObject) -> None:
    rule = _RULES_BY_ID[rule_id]
    secret = data.draw(_STRATEGIES[rule_id], label="secret")
    mode = data.draw(st.integers(min_value=0, max_value=4), label="mode")
    noise = data.draw(_NOISE, label="noise")

    assert_no_plaintext(rule, _mutate(secret, mode, noise))


def test_property_fails_on_a_seeded_unredacted_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Proof the property is not vacuous: with an identity redactor the assertion
    # fires on a real secret shape (a seeded defect must be caught).
    monkeypatch.setattr("test_redaction_properties.redact_secrets", lambda text: (text, ()))
    rule = _RULES_BY_ID["gitleaks/github-pat"]

    with pytest.raises(AssertionError):
        assert_no_plaintext(rule, f"token={rule.example}")


# ---------------------------------------------------------------------------
# Differential: agentwatch recall vs. the pinned oracle
# ---------------------------------------------------------------------------


def _agentwatch_masks(text: str) -> bool:
    masked, kinds = redact_secrets(text)
    return bool(kinds) and masked != text


def _missed_rule_ids(rules: tuple[OracleRule, ...]) -> frozenset[str]:
    return frozenset(rule.id for rule in rules if not _agentwatch_masks(rule.example))


def test_differential_recall_matches_declared_gaps() -> None:
    missed = _missed_rule_ids(ORACLE_RULES)
    assert missed == EXPECTED_GAPS, (
        "differential recall changed: "
        f"newly missed={sorted(missed - EXPECTED_GAPS)}; "
        f"no longer missed={sorted(EXPECTED_GAPS - missed)}"
    )


def test_differential_fails_on_a_new_uncovered_rule() -> None:
    # Proof the differential is not vacuous: an oracle rule class agentwatch does
    # not mask lands in the missed set and would fail the comparison above until
    # it is either implemented or declared in EXPECTED_GAPS.
    synthetic = OracleRule(
        "oracle/synthetic-entropy",
        re.compile(r"XYZSECRET-[0-9]{6}"),
        "XYZSECRET-123456",
    )

    missed = _missed_rule_ids((*ORACLE_RULES, synthetic))

    assert synthetic.id in missed
    assert missed != EXPECTED_GAPS


def test_declared_gaps_are_real_oracle_rules() -> None:
    assert {rule.id for rule in ORACLE_RULES} >= EXPECTED_GAPS


def test_oracle_covers_the_key_rule_classes() -> None:
    ids = {rule.id for rule in ORACLE_RULES}
    for required in (
        "gitleaks/private-key",
        "gitleaks/aws-access-token",
        "gitleaks/github-pat",
        "gitleaks/connection-string",
        "gitleaks/google-api-key",
        "detect-secrets/jwt",
        "detect-secrets/credit-card",
    ):
        assert required in ids


def test_every_strategy_maps_to_a_known_rule() -> None:
    assert set(_STRATEGIES) <= set(_RULES_BY_ID)
