"""Runtime configuration, loaded from environment variables / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "backend" / ".env")

# Hardhat's well-known account #1. Local development ONLY. Never use on a public network.
_DEV_VERIFIER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    rpc_url: str = field(default_factory=lambda: os.getenv("RPC_URL", "http://127.0.0.1:8545"))
    # RPC URL handed to browsers (demo wallets). Defaults to rpc_url; differs inside Docker networks.
    public_rpc_url: str = field(default_factory=lambda: os.getenv("PUBLIC_RPC_URL") or os.getenv("RPC_URL", "http://127.0.0.1:8545"))
    deployment_file: Path = field(
        default_factory=lambda: Path(os.getenv("DEPLOYMENT_FILE", ROOT / "deployments" / "localhost.json"))
    )
    verifier_private_key: str = field(
        default_factory=lambda: os.getenv("VERIFIER_PRIVATE_KEY", _DEV_VERIFIER_KEY)
    )
    # "simulated" = deterministic biome-reference demo data (no network). "sentinel2" = live Sentinel-2 NDVI.
    satellite_provider: str = field(default_factory=lambda: os.getenv("SATELLITE_PROVIDER", "simulated"))
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", ROOT / "backend" / "data")))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()
        )
    )
    # Refuse to sign when the cells are already claimed on-chain (saves gas). The CONTRACT enforces
    # uniqueness regardless; leave false in demos so the on-chain rejection can be shown live.
    refuse_on_conflict: bool = field(default_factory=lambda: _bool("REFUSE_ON_CONFLICT", False))
    attestation_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("ATTESTATION_TTL_SECONDS", "3600")))
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None)
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"))
    pinata_jwt: str | None = field(default_factory=lambda: os.getenv("PINATA_JWT") or None)
    approve_threshold: int = 70  # score out of 100; mirrors MIN_SCORE_BPS (7000) in the contract


def get_settings() -> Settings:
    return Settings()
