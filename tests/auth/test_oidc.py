"""Tests for ``app.auth.oidc.verify_google_token``."""

from __future__ import annotations

import pytest

from app.auth import oidc
from app.auth.oidc import InvalidTokenError, verify_google_token
from tests.auth._google_kit import GoogleOidcTestKit

_AUDIENCE = "test-client-id.apps.googleusercontent.com"


@pytest.fixture(autouse=True)
def _isolate_jwks_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset module-level JWKS cache and inject deterministic test config."""
    oidc._reset_cache_for_tests()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", _AUDIENCE)


def _seed_jwks_cache(monkeypatch: pytest.MonkeyPatch, kit: GoogleOidcTestKit) -> None:
    """Pre-populate the JWKS cache so ``verify_google_token`` does no network fetch."""

    def _fake_fetch() -> dict[str, object]:
        return kit.jwks

    monkeypatch.setattr(oidc, "_fetch_jwks", _fake_fetch)


def test_valid_token_returns_google_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit = GoogleOidcTestKit(audience=_AUDIENCE)
    _seed_jwks_cache(monkeypatch, kit)

    token = kit.sign_token(sub="abc", email="alice@example.com", name="Alice")
    user = verify_google_token(token)

    assert user.sub == "abc"
    assert user.email == "alice@example.com"
    assert user.name == "Alice"


def test_expired_token_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit = GoogleOidcTestKit(audience=_AUDIENCE)
    _seed_jwks_cache(monkeypatch, kit)

    # Signed 1 hour ago with a 60-second lifetime → already expired.
    import time

    token = kit.sign_token(
        issued_at=int(time.time()) - 3600,
        expires_in=60,
    )
    with pytest.raises(InvalidTokenError):
        verify_google_token(token)


def test_wrong_audience_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit = GoogleOidcTestKit(audience=_AUDIENCE)
    _seed_jwks_cache(monkeypatch, kit)

    token = kit.sign_token(audience="some-other-client-id")
    with pytest.raises(InvalidTokenError):
        verify_google_token(token)


def test_tampered_signature_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit = GoogleOidcTestKit(audience=_AUDIENCE)
    _seed_jwks_cache(monkeypatch, kit)

    token = kit.sign_token()
    head, payload, signature = token.split(".")
    tampered = f"{head}.{payload}.{signature[:-4]}AAAA"
    with pytest.raises(InvalidTokenError):
        verify_google_token(tampered)


def test_token_signed_with_wrong_key_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit = GoogleOidcTestKit(audience=_AUDIENCE)
    _seed_jwks_cache(monkeypatch, kit)

    # ``sign_with_wrong_key`` produces a token with an unknown kid; the
    # verifier should refuse rather than verify against an unrelated key.
    token = kit.sign_with_wrong_key()
    with pytest.raises(InvalidTokenError):
        verify_google_token(token)


def test_malformed_token_raises() -> None:
    with pytest.raises(InvalidTokenError):
        verify_google_token("not.a.jwt")


def test_empty_token_raises() -> None:
    with pytest.raises(InvalidTokenError):
        verify_google_token("")


def test_jwks_is_cached_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per ADR-0006, JWKS must be cached so warm invocations skip the fetch."""
    kit = GoogleOidcTestKit(audience=_AUDIENCE)
    call_count = {"n": 0}

    def _counting_fetch() -> dict[str, object]:
        call_count["n"] += 1
        return kit.jwks

    monkeypatch.setattr(oidc, "_fetch_jwks", _counting_fetch)

    for _ in range(3):
        token = kit.sign_token()
        verify_google_token(token)

    assert call_count["n"] == 1


def test_jwks_cache_falls_back_to_stale_on_fetch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per ADR-0006, on fetch failure the cached value is reused regardless of TTL."""
    kit = GoogleOidcTestKit(audience=_AUDIENCE)
    _seed_jwks_cache(monkeypatch, kit)

    # Warm the cache.
    token = kit.sign_token()
    assert verify_google_token(token).sub == "google-sub-123"

    # Force expiry of the TTL window without touching the real clock.
    oidc._cache.fetched_at = 0.0

    def _boom() -> dict[str, object]:
        raise OSError("network down")

    monkeypatch.setattr(oidc, "_fetch_jwks", _boom)

    # Verification must still succeed via the cached (stale) JWKS.
    token2 = kit.sign_token(sub="another-sub")
    user = verify_google_token(token2)
    assert user.sub == "another-sub"
