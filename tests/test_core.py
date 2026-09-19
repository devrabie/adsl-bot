import pytest
import os
from core.security import encrypt_password, decrypt_password
from core.config import settings

def test_encryption_decryption():
    secret = "my_secret_password_123"
    encrypted = encrypt_password(secret)
    assert encrypted != secret
    decrypted = decrypt_password(encrypted)
    assert decrypted == secret

def test_config_admins():
    assert len(settings.admins_list) >= 1
