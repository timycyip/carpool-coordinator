"""Google OIDC token verification with JWKS caching (ADR-0006).

Verifies Google ID tokens by:
  1. Fetching Google's JWKS from https://www.googleapis.com/oauth2/v3/certs.
  2. Caching the JWKS in module-level state with a 1-hour TTL.
  3. Verifying the token's signature, audience (must match GOOGLE_CLIENT_ID),
     and expiry against the cached keys.
  4. Falling back to cached keys when the network fetch fails.

See docs/adr/0006-jwks-caching.md for the full rationale.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import jwt

from app.models.auth import GoogleUser

_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_JWKS_TTL_SECONDS = 3600


class InvalidTokenError(Exception):
    """Raised when a Google ID token fails verification for any reason.

    Covers signature failures, expired tokens, audience mismatches,
    malformed tokens, and missing claims. The message is sanitized —
    callers must not leak internal details to end users.
    """


class _JWKSCache:
    """Module-level JWKS cache per ADR-0006.

    Holds the last successfully fetched JWKS plus its fetch timestamp.
    On a fetch failure, the cached value is preserved (if any) and the
    caller falls back to it regardless of TTL.
    """

    def __init__(self) -> None:
        self.jwks: dict[str, Any] | None = None
        self.fetched_at: float = 0.0

    def is_fresh(self, now: float) -> bool:
        return self.jwks is not None and (now - self.fetched_at) < _JWKS_TTL_SECONDS


_cache = _JWKSCache()


def _reset_cache_for_tests() -> None:
    """Reset module-level JWKS cache. Intended for test fixtures only."""
    _cache.jwks = None
    _cache.fetched_at = 0.0


def _fetch_jwks() -> dict[str, Any]:
    """Fetch the Google JWKS payload over HTTPS.

    Uses urllib so this module has no third-party HTTP dependency at runtime.
    Raises URLError on network failure (handled by caller via cache fallback).
    """
    req = Request(_JWKS_URL, headers={"User-Agent": "carpool-coordinator/1.0"})
    with urlopen(req, timeout=5) as resp:  # noqa: S310 — URL is a hard-coded constant
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise InvalidTokenError("Malformed JWKS response from Google")
    return payload


def _get_jwks() -> dict[str, Any]:
    """Return the cached JWKS or fetch a fresh one.

    Falls back to the cached value (even if expired) on network failure,
    per ADR-0006. Raises InvalidTokenError only when the cache is empty
    AND the network fetch fails.
    """
    now = time.time()
    if _cache.is_fresh(now):
        return _cache.jwks  # type: ignore[return-value]
    try:
        fresh = _fetch_jwks()
    except (URLError, TimeoutError, OSError):
        if _cache.jwks is not None:
            return _cache.jwks
        raise InvalidTokenError("Unable to verify token: JWKS unavailable") from None
    _cache.jwks = fresh
    _cache.fetched_at = now
    return fresh


def _jwk_for_kid(jwks: dict[str, Any], kid: str | None) -> dict[str, Any]:
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        raise InvalidTokenError("Google JWKS contained no signing keys")
    if kid is None:
        raise InvalidTokenError("Token header missing kid")
    for key in keys:
        if isinstance(key, dict) and key.get("kid") == kid:
            return key
    raise InvalidTokenError("No JWKS key matches token kid")


def _jwk_to_pem(jwk: dict[str, Any]) -> str:
    """Convert a single JWK dict into a PEM-encoded public key string."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    if not isinstance(public_key, RSAPublicKey):
        raise InvalidTokenError("JWK did not yield an RSA public key")
    pem = public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode("ascii")


def _required_audience() -> str:
    aud = os.environ.get("GOOGLE_CLIENT_ID")
    if not aud:
        raise InvalidTokenError("Server is missing GOOGLE_CLIENT_ID configuration")
    return aud


def verify_google_token(id_token: str) -> GoogleUser:
    """Verify a Google ID token and return the authenticated user.

    Verifies signature against Google's cached JWKS, audience against
    ``GOOGLE_CLIENT_ID``, and expiry. Returns a GoogleUser on success.
    Raises InvalidTokenError on any failure.
    """
    if not isinstance(id_token, str) or not id_token:
        raise InvalidTokenError("id_token must be a non-empty string")

    jwks = _get_jwks()

    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Malformed token") from exc

    kid = unverified_header.get("kid")
    jwk = _jwk_for_kid(jwks, kid)
    public_key_pem = _jwk_to_pem(jwk)
    audience = _required_audience()

    try:
        claims = jwt.decode(
            id_token,
            key=public_key_pem,
            algorithms=["RS256"],
            audience=audience,
            options={"require": ["exp", "iat", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise InvalidTokenError("Token audience does not match") from exc
    except jwt.InvalidSignatureError as exc:
        raise InvalidTokenError("Token signature is invalid") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token verification failed") from exc

    sub = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name") or email
    if not isinstance(sub, str) or not sub:
        raise InvalidTokenError("Token missing sub claim")
    if not isinstance(email, str) or not email:
        raise InvalidTokenError("Token missing email claim")

    return GoogleUser(sub=sub, email=email, name=str(name))


__all__ = ["InvalidTokenError", "verify_google_token"]
