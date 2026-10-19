"""EIP-712 attestation signing. Must match `CarbonTraceRegistry.sol` exactly."""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass

from eth_account import Account
from eth_utils import keccak, to_checksum_address

ATTESTATION_TYPES = [
    {"name": "to", "type": "address"},
    {"name": "vintage", "type": "uint16"},
    {"name": "centroidLatE6", "type": "int32"},
    {"name": "centroidLonE6", "type": "int32"},
    {"name": "cellsHash", "type": "bytes32"},
    {"name": "tonnes", "type": "uint256"},
    {"name": "scoreBps", "type": "uint16"},
    {"name": "evidenceHash", "type": "bytes32"},
    {"name": "metadataHash", "type": "bytes32"},
    {"name": "deadline", "type": "uint256"},
    {"name": "nonce", "type": "uint256"},
]

DOMAIN_TYPES = [
    {"name": "name", "type": "string"},
    {"name": "version", "type": "string"},
    {"name": "chainId", "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
]


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def keccak_hex(data: bytes) -> str:
    return "0x" + keccak(data).hex()


def cells_hash(cells: list[int]) -> bytes:
    """keccak256(abi.encodePacked(uint64[])): every element is left-padded to 32 bytes."""
    return keccak(b"".join(c.to_bytes(32, "big") for c in cells))


@dataclass(frozen=True)
class SignedAttestation:
    message: dict  # JSON-safe (ints for numbers, 0x-hex for bytes32)
    signature: str
    signer: str


def sign_attestation(
    *, private_key: str, chain_id: int, registry: str, to: str, vintage: int, centroid_lat_e6: int,
    centroid_lon_e6: int, cells: list[int], tonnes: int, score_bps: int, evidence_hash: str,
    metadata_uri: str, ttl_seconds: int,
) -> SignedAttestation:
    message = {
        "to": to_checksum_address(to),
        "vintage": vintage,
        "centroidLatE6": centroid_lat_e6,
        "centroidLonE6": centroid_lon_e6,
        "cellsHash": "0x" + cells_hash(cells).hex(),
        "tonnes": tonnes,
        "scoreBps": score_bps,
        "evidenceHash": evidence_hash,
        "metadataHash": "0x" + keccak(metadata_uri.encode("utf-8")).hex(),
        "deadline": int(time.time()) + ttl_seconds,
        "nonce": secrets.randbits(255),
    }
    full = {
        "types": {"EIP712Domain": DOMAIN_TYPES, "Attestation": ATTESTATION_TYPES},
        "primaryType": "Attestation",
        "domain": {"name": "CarbonTraceRegistry", "version": "1", "chainId": chain_id,
                   "verifyingContract": to_checksum_address(registry)},
        "message": message,
    }
    signed = Account.sign_typed_data(private_key, full_message=full)
    return SignedAttestation(message=message, signature="0x" + signed.signature.hex().removeprefix("0x"),
                             signer=Account.from_key(private_key).address)
