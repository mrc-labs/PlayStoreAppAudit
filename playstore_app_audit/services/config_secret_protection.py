from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from playstore_app_audit.platform.machine_identity import (
    local_machine_identity,
    local_user_identity,
)

_ENVELOPE_VERSION = "v1"
_SALT_BYTES = 16
_NONCE_BYTES = 12
_KEY_BYTES = 32
_CONTEXT = b"PlayStoreAppAudit|config-secret-protection|aptoide-api-key|v1"
# This application-specific material is intentionally only one component of a
# machine/user-bound derivation. It is not hardware-backed or secret against
# reverse engineering of the distributed application.
_APP_KEY_MATERIAL = b"psaa-v1.99-local-config-aead-2026-5f87c4e1"


@dataclass(frozen=True, slots=True)
class SecretDecryptionResult:
    available: bool
    value: str = field(default="", repr=False)
    message: str = ""


def _derive_key(salt: bytes) -> bytes:
    identity = "\0".join((local_machine_identity(), local_user_identity())).encode()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_BYTES,
        salt=salt,
        info=_CONTEXT,
    ).derive(_APP_KEY_MATERIAL + b"\0" + identity)


def protect_secret(secret: str) -> str:
    plaintext = str(secret or "").encode("utf-8")
    if not plaintext:
        return ""
    salt = os.urandom(_SALT_BYTES)
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = AESGCM(_derive_key(salt)).encrypt(nonce, plaintext, _CONTEXT)
    payload = base64.urlsafe_b64encode(salt + nonce + ciphertext).decode("ascii").rstrip("=")
    return f"{_ENVELOPE_VERSION}:{payload}"


def unprotect_secret(envelope: object) -> SecretDecryptionResult:
    text = str(envelope or "").strip()
    if not text:
        return SecretDecryptionResult(False, message="No saved credential is configured.")
    version, separator, encoded = text.partition(":")
    if not separator or version != _ENVELOPE_VERSION:
        return SecretDecryptionResult(False, message="Unsupported or malformed credential format.")
    try:
        padded = encoded + ("=" * (-len(encoded) % 4))
        payload = base64.b64decode(padded, altchars=b"-_", validate=True)
        if len(payload) <= _SALT_BYTES + _NONCE_BYTES + 16:
            raise ValueError("credential envelope is too short")
        salt = payload[:_SALT_BYTES]
        nonce = payload[_SALT_BYTES : _SALT_BYTES + _NONCE_BYTES]
        ciphertext = payload[_SALT_BYTES + _NONCE_BYTES :]
        plaintext = AESGCM(_derive_key(salt)).decrypt(nonce, ciphertext, _CONTEXT)
        value = plaintext.decode("utf-8")
        if not value:
            raise ValueError("empty credential")
        return SecretDecryptionResult(True, value=value)
    except (InvalidTag, ValueError, UnicodeError):
        return SecretDecryptionResult(
            False,
            message=(
                "Saved Aptoide credentials cannot be used on this device. "
                "Please enter the API key again."
            ),
        )
