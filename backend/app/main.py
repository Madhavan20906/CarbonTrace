"""CarbonTrace AI verifier API."""
from __future__ import annotations

import datetime as dt
import logging
from contextlib import asynccontextmanager

from eth_utils import is_address, to_checksum_address
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from . import geo
from .attest import SignedAttestation, canonical_json, sign_attestation
from .chain import Chain, ChainUnavailable
from .config import Settings, get_settings
from .evidence import EvidenceStore, pin_to_ipfs
from .explain import explain
from .satellite import ProviderUnavailable, get_provider
from .scenarios import SCENARIOS
from .scoring import MODEL_VERSION, assess

log = logging.getLogger("carbontrace")


class VerifyRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    developer: str
    vintage: int = Field(ge=2015, le=dt.date.today().year)
    polygon: list = Field(description="GeoJSON Polygon coordinates [[[lon,lat],...]] or a bare ring [[lon,lat],...]")
    claimed_tonnes: int = Field(gt=0, le=10_000_000)
    project_type: str = Field(default="reforestation", pattern="^(reforestation|conservation)$")

    @field_validator("developer")
    @classmethod
    def _addr(cls, v: str) -> str:
        if not is_address(v):
            raise ValueError("developer must be a valid 0x wallet address")
        return to_checksum_address(v)


def create_app(settings: Settings | None = None, chain_factory=Chain) -> FastAPI:
    settings = settings or get_settings()
    state: dict = {}

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            state["chain"] = chain_factory(settings)
        except ChainUnavailable as e:
            log.warning("%s", e)
            state["chain"] = None
        yield

    app = FastAPI(title="CarbonTrace Verifier", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"],
                       allow_headers=["*"])
    store = EvidenceStore(settings.data_dir)
    provider = get_provider(settings.satellite_provider)

    def chain() -> Chain:
        c = state.get("chain")
        if c is None:
            raise HTTPException(503, "Registry contract not configured. Deploy it and set DEPLOYMENT_FILE.")
        return c

    @app.get("/api/health")
    def health():
        c = state.get("chain")
        return {"ok": True, "chainConfigured": c is not None, "chainConnected": bool(c and c.connected()),
                "satelliteProvider": settings.satellite_provider, "model": MODEL_VERSION}

    @app.get("/api/config")
    def config():
        c = chain()
        from eth_account import Account
        return {**c.info(), "rpcUrl": settings.public_rpc_url, "satelliteProvider": settings.satellite_provider,
                "simulated": settings.satellite_provider == "simulated", "approveThreshold": settings.approve_threshold,
                "verifierSigner": Account.from_key(settings.verifier_private_key).address,
                "model": MODEL_VERSION, "llmExplanations": bool(settings.anthropic_api_key)}

    @app.get("/api/scenarios")
    def scenarios():
        return SCENARIOS

    @app.post("/api/verify")
    async def verify(req: VerifyRequest):
        try:
            geometry = geo.analyse(req.polygon)
        except geo.GeometryError as e:
            raise HTTPException(422, str(e)) from e

        try:
            sat = await provider.observe(geometry, req.vintage)
        except ProviderUnavailable as e:
            raise HTTPException(503, str(e)) from e
        except Exception as e:  # network or data errors from a live provider
            log.exception("satellite provider failed")
            raise HTTPException(502, f"Satellite data provider failed: {e}") from e

        a = assess(geometry, sat, req.claimed_tonnes, settings.approve_threshold)
        text, author = await explain(a, req.name, settings.anthropic_api_key, settings.anthropic_model)

        c = state.get("chain")
        conflict = None
        if c is not None:
            try:
                conflict = await run_in_threadpool(c.find_conflict, req.vintage, geometry.cells)
            except Exception:
                log.exception("conflict pre-check failed")

        signed_ok = a.approved and not (conflict and settings.refuse_on_conflict)
        bundle = {
            "schema": "carbontrace.evidence/1",
            "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "project": {"name": req.name, "developer": req.developer, "vintage": req.vintage,
                        "type": req.project_type, "claimedTonnes": req.claimed_tonnes},
            "geometry": {"ring": geometry.ring, "areaHa": round(geometry.area_ha, 3),
                         "centroid": [geometry.centroid_lon, geometry.centroid_lat], "cells": geometry.cells,
                         "cellSizeMicroDeg": geo.CELL_SIZE_MICRODEG},
            "satellite": sat.to_dict(),
            "assessment": a.to_dict(),
            "explanation": {"text": text, "author": author},
        }
        evidence_hash = store.put(bundle)

        response = {
            "approved": a.approved, "score": a.score, "verifiedTonnes": a.verified_tonnes,
            "capacityTonnes": a.capacity_tonnes, "claimedTonnes": a.claimed_tonnes, "checks": [vars(x) for x in a.checks],
            "metrics": a.metrics, "components": a.components, "capsApplied": a.caps_applied,
            "explanation": text, "explanationBy": author, "modelVersion": a.model_version,
            "simulated": sat.simulated, "satellite": {"provider": sat.provider, "biome": sat.biome,
                                                        "observations": [vars(o) for o in sat.observations],
                                                        "notes": sat.notes, "lowConfidence": sat.low_confidence},
            "geometry": {"ring": geometry.ring, "areaHa": round(geometry.area_ha, 2), "cells": len(geometry.cells),
                         "centroid": [geometry.centroid_lon, geometry.centroid_lat]},
            "evidenceHash": evidence_hash, "chainConflict": conflict, "signed": False, "attestation": None,
        }
        if not signed_ok:
            if a.approved and conflict:
                response["explanation"] += (f" The land overlaps project #{conflict['projectId']} for {req.vintage}, "
                                            "so no attestation was issued.")
            return response

        if c is None:
            raise HTTPException(503, "Registry contract not configured; cannot sign an attestation.")

        metadata_uri = f"{settings.public_base_url}/api/evidence/{evidence_hash}"
        if settings.pinata_jwt:
            cid = await pin_to_ipfs(bundle, settings.pinata_jwt)
            if cid:
                metadata_uri = f"ipfs://{cid}"
        sa: SignedAttestation = sign_attestation(
            private_key=settings.verifier_private_key, chain_id=c.chain_id, registry=c.address, to=req.developer,
            vintage=req.vintage, centroid_lat_e6=geometry.centroid_lat_e6, centroid_lon_e6=geometry.centroid_lon_e6,
            cells=geometry.cells, tonnes=a.verified_tonnes, score_bps=a.score * 100, evidence_hash=evidence_hash,
            metadata_uri=metadata_uri, ttl_seconds=settings.attestation_ttl_seconds,
        )
        response["signed"] = True
        response["attestation"] = {
            "message": {k: (str(v) if k in ("tonnes", "deadline", "nonce") else v) for k, v in sa.message.items()},
            "signature": sa.signature, "signer": sa.signer, "cells": [str(x) for x in geometry.cells],
            "metadataURI": metadata_uri,
        }
        return response

    @app.get("/api/evidence/{hash_hex}")
    def evidence(hash_hex: str):
        raw = store.get_raw(hash_hex)
        if raw is None:
            raise HTTPException(404, "Evidence bundle not found.")
        return Response(content=raw, media_type="application/json")

    @app.get("/api/projects")
    def projects():
        return chain().projects()

    @app.get("/api/projects/{pid}")
    def project(pid: int):
        p = chain().project(pid)
        if p is None:
            raise HTTPException(404, "Unknown project.")
        return p

    @app.get("/api/stats")
    def stats():
        return chain().stats()

    @app.get("/api/activity")
    def activity():
        return chain().activity()

    return app


app = create_app()
