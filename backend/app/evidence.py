"""Content-addressed evidence bundles. The keccak256 of the canonical JSON is committed on-chain."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from .attest import canonical_json, keccak_hex


class EvidenceStore:
    def __init__(self, directory: Path):
        self.dir = Path(directory) / "evidence"
        self.dir.mkdir(parents=True, exist_ok=True)

    def put(self, bundle: dict) -> str:
        raw = canonical_json(bundle)
        h = keccak_hex(raw)
        path = self.dir / f"{h[2:]}.json"
        if not path.exists():
            path.write_bytes(raw)
        return h

    def get_raw(self, hash_hex: str) -> bytes | None:
        """The exact bytes that were hashed. Clients can keccak256 them and compare with the on-chain hash."""
        h = hash_hex.lower().removeprefix("0x")
        if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
            return None
        path = self.dir / f"{h}.json"
        return path.read_bytes() if path.exists() else None

    def get(self, hash_hex: str) -> dict | None:
        raw = self.get_raw(hash_hex)
        return json.loads(raw) if raw is not None else None


async def pin_to_ipfs(bundle: dict, jwt: str) -> str | None:
    """Optional: pin the bundle on IPFS through Pinata and return the CID (None on failure)."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.pinata.cloud/pinning/pinJSONToIPFS",
                headers={"Authorization": f"Bearer {jwt}"},
                json={"pinataContent": bundle, "pinataMetadata": {"name": "carbontrace-evidence"}},
            )
            r.raise_for_status()
            return r.json()["IpfsHash"]
    except Exception:
        return None
