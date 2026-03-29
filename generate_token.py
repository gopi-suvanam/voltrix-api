"""
Run this script once to generate a secure API token and its SHA-256 hash.

Usage:
    .env/Scripts/python generate_token.py

Copy the printed token — you will need it in the Authorization header:
    Authorization: Bearer <token>

Copy the hash line into config.env:
    API_TOKEN_HASH=<hash>

The raw token is NOT stored anywhere. Keep it safe.
"""

import hashlib
import secrets

token = secrets.token_hex(32)          # 64-char hex string, 256 bits of entropy
token_hash = hashlib.sha256(token.encode()).hexdigest()

print()
print("=" * 60)
print("  Bearer Token (keep this secret, share with API clients)")
print("=" * 60)
print(f"  {token}")
print()
print("=" * 60)
print("  Add this line to config.env")
print("=" * 60)
print(f"  API_TOKEN_HASH={token_hash}")
print()
