"""Helpers for testing Google OIDC verification without network calls."""

from __future__ import annotations

import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_KID = "test-key-1"


def _new_rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _private_pem(key: rsa.RSAPrivateKey) -> str:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def _public_jwk(key: rsa.RSAPrivateKey) -> dict[str, object]:
    public_numbers = key.public_key().public_numbers()
    import base64

    def _b64u(value: int) -> str:
        byte_len = (value.bit_length() + 7) // 8
        return (
            base64.urlsafe_b64encode(value.to_bytes(byte_len, "big"))
            .rstrip(b"=")
            .decode("ascii")
        )

    return {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": _KID,
        "n": _b64u(public_numbers.n),
        "e": _b64u(public_numbers.e),
    }


class GoogleOidcTestKit:
    """Generates a self-signed RSA keypair, JWKS, and ID-token signer.

    Lets test fixtures produce tokens that the production verifier will
    accept, without ever touching the real Google JWKS endpoint.
    """

    def __init__(self, audience: str = "test-client-id") -> None:
        self.audience = audience
        self._key = _new_rsa_keypair()

    @property
    def jwks(self) -> dict[str, object]:
        return {"keys": [_public_jwk(self._key)]}

    @property
    def kid(self) -> str:
        return _KID

    def sign_token(
        self,
        sub: str = "google-sub-123",
        email: str = "user@example.com",
        name: str = "Test User",
        audience: str | None = None,
        expires_in: int = 3600,
        issued_at: int | None = None,
        extra_claims: dict[str, object] | None = None,
    ) -> str:
        now = int(time.time()) if issued_at is None else issued_at
        claims: dict[str, object] = {
            "sub": sub,
            "email": email,
            "name": name,
            "iat": now,
            "exp": now + expires_in,
            "aud": audience if audience is not None else self.audience,
        }
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(
            claims,
            _private_pem(self._key),
            algorithm="RS256",
            headers={"kid": self.kid},
        )

    def sign_with_wrong_key(self, **kwargs: object) -> str:
        other = _new_rsa_keypair()
        now = int(time.time())
        claims: dict[str, object] = {
            "sub": "google-sub-123",
            "email": "user@example.com",
            "name": "Test User",
            "iat": now,
            "exp": now + 3600,
            "aud": self.audience,
        }
        claims.update(kwargs)
        return jwt.encode(
            claims,
            _private_pem(other),
            algorithm="RS256",
            headers={"kid": "different-kid"},
        )
