"""Generate a fresh verifier key for a public deployment.

    python scripts/gen_verifier_key.py

Put the private key in backend/.env as VERIFIER_PRIVATE_KEY and the address in contracts-pkg/.env as VERIFIER_ADDRESS.
Keep the private key out of git. In production hold it in a KMS/HSM and rotate with VERIFIER_ROLE grants.
"""
from eth_account import Account

acct = Account.create()
print(f"VERIFIER_PRIVATE_KEY={acct.key.hex()}")
print(f"VERIFIER_ADDRESS={acct.address}")
