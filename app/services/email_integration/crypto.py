"""
app/services/email_integration/crypto.py

Encrypt/decrypt OAuth tokens at rest using Fernet symmetric encryption.
Key comes from EMAIL_TOKEN_ENCRYPTION_KEY env var.
"""

import structlog
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = structlog.get_logger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.email_token_encryption_key
        if not key:
            raise RuntimeError(
                "EMAIL_TOKEN_ENCRYPTION_KEY is not set. "
                "Generate one with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string, return base64-encoded ciphertext."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted token."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("token_decryption_failed", hint="Key may have been rotated")
        raise ValueError("Failed to decrypt OAuth token — encryption key may have changed")
