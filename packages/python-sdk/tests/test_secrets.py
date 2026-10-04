"""Tests for secret/PII detection and masking (M4 4.2).

Detection is the trust boundary for R7: no secret/PII may survive to the store.
"""

from __future__ import annotations

from types import MappingProxyType

from agentwatch.secrets import SECRET_KINDS, detect, redact_mapping, redact_secrets


def test_api_key_masked_to_redacted_kind() -> None:
    masked, kinds = redact_secrets("token sk-abcdefgh")
    assert masked == "token <REDACTED:api-key>"
    assert kinds == ("api-key",)


def test_short_or_bare_prefix_is_not_redacted() -> None:
    assert redact_secrets("sk-") == ("sk-", ())
    assert redact_secrets("AKIA short") == ("AKIA short", ())
    assert redact_secrets("hello world") == ("hello world", ())


def test_github_and_slack_and_gcp_prefixes() -> None:
    assert redact_secrets("ghp_" + "a" * 36)[1] == ("api-key",)
    assert redact_secrets("xoxb-" + "1" * 12 + "-abcdef")[1] == ("api-key",)
    assert redact_secrets("AIza" + "b" * 30)[1] == ("api-key",)


def test_aws_access_key_id_is_api_key() -> None:
    assert redact_secrets("AKIAIOSFODNN7EXAMPLE")[1] == ("api-key",)


def test_bearer_token() -> None:
    masked, kinds = redact_secrets("Authorization: Bearer abc.def.ghi")
    assert kinds == ("oauth-bearer",)
    assert "abc.def.ghi" not in masked


def test_private_key_header() -> None:
    assert redact_secrets("-----BEGIN RSA PRIVATE KEY-----")[1] == ("private-key",)


def test_private_key_block_masks_the_key_material() -> None:
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA1234567890SECRETMATERIAL\n"
        "-----END RSA PRIVATE KEY-----"
    )
    masked, kinds = redact_secrets(pem)

    assert kinds == ("private-key",)
    assert "SECRETMATERIAL" not in masked


def test_substring_prefixes_are_not_false_positives() -> None:
    assert redact_secrets("risk-assessment and disk-usage") == (
        "risk-assessment and disk-usage",
        (),
    )
    assert redact_secrets("task-manager ask-me-anything") == ("task-manager ask-me-anything", ())


def test_bearer_of_good_news_is_not_a_token() -> None:
    assert redact_secrets("Bearer of good news") == ("Bearer of good news", ())


def test_bare_and_camel_case_sensitive_keys_are_masked() -> None:
    masked, kinds = redact_mapping(
        {"PASSWORD": "p", "TOKEN": "t", "apiKey": "k", "accessToken": "a", "n": 1}
    )

    assert masked == {
        "PASSWORD": "<REDACTED:env-secret>",
        "TOKEN": "<REDACTED:env-secret>",
        "apiKey": "<REDACTED:env-secret>",
        "accessToken": "<REDACTED:env-secret>",
        "n": 1,
    }
    assert kinds == ("env-secret",)


def test_non_string_value_under_sensitive_key_is_masked() -> None:
    masked, kinds = redact_mapping({"PASSWORD": {"nested": "x"}})
    assert masked == {"PASSWORD": "<REDACTED:env-secret>"}
    assert kinds == ("env-secret",)


def test_jwt() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    assert redact_secrets(jwt)[1] == ("jwt",)


def test_email_and_ssn_and_phone() -> None:
    assert redact_secrets("mail a.b@example.com")[0] == "mail <REDACTED:email>"
    assert redact_secrets("ssn 123-45-6789")[0] == "ssn <REDACTED:ssn>"
    assert redact_secrets("call +14155552671")[0] == "call <REDACTED:phone>"


def test_credit_card_uses_luhn() -> None:
    assert redact_secrets("card 4111 1111 1111 1111")[1] == ("credit-card",)
    # One digit changed: fails Luhn, must not be redacted.
    assert redact_secrets("card 4111 1111 1111 1112")[1] == ()


def test_connection_string_with_credentials() -> None:
    masked, kinds = redact_secrets("db postgres://user:pass@host:5432/app")
    assert kinds == ("connection-string",)
    assert "pass" not in masked


def test_env_var_name_denylist_masks_value() -> None:
    masked, kinds = redact_mapping({"MY_SECRET": "plainvalue", "note": "hi"})
    assert masked == {"MY_SECRET": "<REDACTED:env-secret>", "note": "hi"}
    assert kinds == ("env-secret",)


def test_redact_mapping_recurses_and_dedupes() -> None:
    masked, kinds = redact_mapping(
        {"args": ["sk-abcdefgh", "sk-ijklmnop"], "n": 3, "more": {"k": "sk-abcdefgh"}}
    )
    assert masked["args"] == ["<REDACTED:api-key>", "<REDACTED:api-key>"]
    assert masked["n"] == 3
    assert masked["more"] == {"k": "<REDACTED:api-key>"}
    assert kinds == ("api-key",)


def test_secret_kinds_are_stable_and_ordered() -> None:
    assert "api-key" in SECRET_KINDS
    assert detect("sk-abcdefgh")[0].kind == "api-key"


def test_redact_mapping_accepts_any_mapping() -> None:
    masked, kinds = redact_mapping(MappingProxyType({"cmd": "sk-abcdefgh"}))
    assert masked["cmd"] == "<REDACTED:api-key>"
    assert kinds == ("api-key",)


def test_credit_card_does_not_eat_following_text() -> None:
    masked, kinds = redact_secrets("card 4111 1111 1111 1111 ssn")
    assert masked == "card <REDACTED:credit-card> ssn"
    assert kinds == ("credit-card",)
