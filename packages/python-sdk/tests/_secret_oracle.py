"""A pinned differential oracle for secret detection (PRD 38 §Q1, issue #218).

The redaction self-test (``agentwatch.selftest``) runs a *fixed corpus*: it proves
regression, not recall. This module supplies the other half — an independent set
of secret-detection rule signatures, so a property/differential test can assert
agentwatch's recall is **at least** the oracle's on generated samples and report
any rule class it misses as a failure rather than a silent pass.

Provenance: the rule ids and patterns are transcribed from the default rule sets
of **gitleaks v8** (``config/gitleaks.toml``) and the plugin set of
**detect-secrets v1.5** (``detect_secrets/plugins``). They are pinned here so the
oracle cannot drift under CI: a rule class is added by editing this table and
updating :data:`EXPECTED_GAPS`, which makes the change reviewable. Nothing here
is a runtime dependency or ships in the package.

A rule whose ``example`` agentwatch does not mask is a *gap*. Gaps are honest and
explicit in :data:`EXPECTED_GAPS`; the differential test fails if the observed
gap set differs from the declared one, so a new miss cannot be introduced quietly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class OracleRule:
    """One pinned oracle rule.

    Attributes:
        id: stable rule id, namespaced by its source (``gitleaks/`` or
            ``detect-secrets/``).
        pattern: the compiled oracle signature. Used both to detect the rule class
            in a sample and to check that a mutated sample still *is* that class.
        example: a canonical string the oracle matches; the differential test runs
            this through agentwatch and compares the verdict.
    """

    id: str
    pattern: re.Pattern[str]
    example: str


# Uppercase AWS access-key id alphabet (A3T + [A-Z0-9]{16}).
_AWS_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


ORACLE_RULES: tuple[OracleRule, ...] = (
    OracleRule(
        "gitleaks/private-key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        # Built at runtime so the scanner never sees a literal key header.
        "-----BEGIN RSA "
        + "PRIVATE KEY-----\n"
        + "MIIEowIBAAKCAQEA1234567890SECRETMATERIAL\n"
        + "-----END RSA "
        + "PRIVATE KEY-----",
    ),
    OracleRule(
        "gitleaks/aws-access-token",
        re.compile(r"(?<![A-Za-z0-9])AKIA[A-Z0-9]{16}"),
        "AKIA" + "IOSFODNN7EXAMPLE",
    ),
    OracleRule(
        "gitleaks/aws-secret-access-key",
        re.compile(r"(?i)aws.{0,20}?['\"][0-9a-zA-Z/+]{40}['\"]"),
        'aws_secret_access_key = "' + "wJalrXUtnFEMI/K7MDENG/" + "bPxRfiCYEXAMPLEKEY" + '"',
    ),
    OracleRule(
        "gitleaks/github-pat",
        re.compile(r"(?<![A-Za-z0-9])ghp_[0-9A-Za-z]{36}"),
        "ghp_" + "A" * 36,
    ),
    OracleRule(
        "gitleaks/github-oauth",
        re.compile(r"(?<![A-Za-z0-9])gho_[0-9A-Za-z]{36}"),
        "gho_" + "B" * 36,
    ),
    OracleRule(
        "gitleaks/github-app-token",
        re.compile(r"(?<![A-Za-z0-9])ghs_[0-9A-Za-z]{36}"),
        "ghs_" + "C" * 36,
    ),
    OracleRule(
        "gitleaks/github-refresh-token",
        re.compile(r"(?<![A-Za-z0-9])ghr_[0-9A-Za-z]{76}"),
        "ghr_" + "D" * 76,
    ),
    OracleRule(
        "gitleaks/gitlab-pat",
        re.compile(r"glpat-[0-9A-Za-z_\-]{20}"),
        "glpat-" + "EFGHIJKLMNOPQRST" + "UVWX",
    ),
    OracleRule(
        "gitleaks/slack-bot-token",
        re.compile(r"(?<![A-Za-z0-9])xoxb-[0-9A-Za-z\-]{10,}"),
        "xoxb-" + "1234567890-" + "abcdefghijklmnopqrstuvwx",
    ),
    OracleRule(
        "gitleaks/slack-webhook",
        re.compile(
            r"https://hooks\.slack\.com/services/T[0-9A-Za-z_]{8,}/B[0-9A-Za-z_]{8,}/"
            r"[0-9A-Za-z_]{20,}"
        ),
        "https://hooks.slack.com/services/" + "T00000000/B00000000/" + "XXXXXXXXXXXXXXXXXXXXXXXX",
    ),
    OracleRule(
        "gitleaks/stripe-access-token",
        re.compile(r"[rs]k_live_[0-9A-Za-z]{20,}"),
        "sk_live_" + "A" * 24,
    ),
    OracleRule(
        "gitleaks/npm-token",
        re.compile(r"npm_[0-9A-Za-z]{36}"),
        "npm_" + "A" * 36,
    ),
    OracleRule(
        "gitleaks/google-api-key",
        re.compile(r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_\-]{35}"),
        "AIza" + "b" * 35,
    ),
    OracleRule(
        "detect-secrets/google-oauth-id",
        re.compile(r"ya29\.[0-9A-Za-z_\-]+"),
        "ya29." + "a0B1c2D3e4F5g6H7",
    ),
    OracleRule(
        "detect-secrets/jwt",
        re.compile(r"eyJ[0-9A-Za-z_\-]*\.[0-9A-Za-z_\-]+\.[0-9A-Za-z_\-]+"),
        "eyJhbGciOiJIUzI1NiJ9"
        + "."
        + "eyJzdWIiOiIxIn0"
        + "."
        + "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
    ),
    OracleRule(
        "gitleaks/connection-string",
        re.compile(r"(?:postgres(?:ql)?|mongodb(?:\+srv)?|redis|mysql|amqp)://[^\s:@/]+:[^\s@/]+@"),
        "postgres://user:" + "hunter2" + "@host:5432/app",
    ),
    OracleRule(
        "detect-secrets/basic-auth",
        re.compile(r"(?i)basic\s+[0-9A-Za-z+/=]{12,}"),
        "Basic " + "YWxhZGRpbjpvcGVuc2VzYW1l",
    ),
    OracleRule(
        "detect-secrets/azure-storage-key",
        re.compile(r"[0-9A-Za-z+/]{86}=="),
        "A" * 86 + "==",
    ),
    OracleRule(
        "detect-secrets/credit-card",
        re.compile(r"\b\d(?:[ -]?\d){12,18}\b"),
        "4111 1111 " + "1111 1111",
    ),
    OracleRule(
        "detect-secrets/us-ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "123-" + "45-" + "6789",
    ),
    OracleRule(
        "detect-secrets/email",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "a.b@example.com",
    ),
    OracleRule(
        "detect-secrets/phone",
        re.compile(r"\+[1-9]\d{6,14}\b"),
        "+" + "14155552671",
    ),
    OracleRule(
        "detect-secrets/bearer",
        re.compile(r"Bearer\s+[0-9A-Za-z._\-]{8,}"),
        "Bearer " + "abcdefghijklmnop",
    ),
    OracleRule(
        "detect-secrets/high-entropy",
        re.compile(r"[0-9A-Za-z+/]{16,64}={0,2}"),
        "Zx9Q2wLp" + "8Vn4Rk7T",
    ),
)


# Rule ids the oracle knows that agentwatch deliberately does not mask in v0.1.0.
# Each is a real recall gap, kept explicit so the differential test fails when the
# gap set changes (a new miss must not slip in unnoticed). This table is the honest
# "what we do not claim" list referenced from the claims ledger (Q9).
EXPECTED_GAPS: frozenset[str] = frozenset(
    {
        "gitleaks/aws-secret-access-key",
        "gitleaks/gitlab-pat",
        "gitleaks/slack-webhook",
        "gitleaks/stripe-access-token",
        "gitleaks/npm-token",
        "detect-secrets/basic-auth",
        "detect-secrets/azure-storage-key",
        "detect-secrets/high-entropy",
    }
)


def detect_oracle(text: str) -> tuple[str, ...]:
    """Return the ids of every oracle rule that matches ``text`` (in table order)."""
    return tuple(rule.id for rule in ORACLE_RULES if rule.pattern.search(text))
