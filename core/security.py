import base64
from cryptography.fernet import Fernet
from core.config import settings

def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY.strip()
    # If the key is not 32 URL-safe base64-encoded bytes, fallback or derive key
    try:
        return Fernet(key.encode('utf-8'))
    except Exception:
        # Fallback to deterministic Fernet key generation if invalid key in env
        padded_key = base64.urlsafe_b64encode(key.zfill(32)[:32].encode('utf-8'))
        return Fernet(padded_key)

def encrypt_password(password: str) -> str:
    f = _get_fernet()
    return f.encrypt(password.encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_password: str) -> str:
    f = _get_fernet()
    return f.decrypt(encrypted_password.encode('utf-8')).decode('utf-8')
