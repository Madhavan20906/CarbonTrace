"""Deterministic plausibility scoring for forest carbon claims.

The score decides whether an attestation is signed. It is a pure function of the satellite observations,
the polygon and the claim, so any auditor can re-run it on the published evidence bundle and get the same
answer. The LLM never influences the decision, it only writes the human-readable explanation.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass, field

from .geo import Geometry
from .satellite import SatelliteResult

APPROVE_THRESHOLD = 70
MODEL_VERSION = "carbontrace-score-1.0"


@dataclass
class Check:
    id: str
    label: str
    status: str  # pass | warn | fail
    value: str
    detail: str


@dataclass
class Assessment:
    score: int
    approved: bool
    verified_tonnes: int
    capacity_tonnes: float
    claimed_tonnes: int
    checks: list[Check]
    metrics: dict
    components: dict
    caps_applied: list[str] = field(default_factory=list)
    model_version: str = MODEL_VERSION

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def assess(geom: Geometry, sat: SatelliteResult, claimed_tonnes: int, threshold: int = APPROVE_THRESHOLD) -> Assessment:
    obs = sorted(sat.observations, key=lambda o: o.month)
    usable = [o for o in obs if o.valid_fraction >= 0.3]

    if not usable:
        checks = [Check("coverage", "Usable satellite observations", "fail", "0 of 12 months",
                        "No cloud-free observations were available for this site and year.")]
        return Assessment(0, False, 0, 0.0, claimed_tonnes, checks, {"months_observed": 0}, {}, ["no_observations"])

    weights = [o.valid_fraction for o in usable]
    canopy = sum(o.canopy_fraction * w for o, w in zip(usable, weights)) / sum(weights)
    means = [o.mean_ndvi for o in usable]
    median_ndvi = statistics.median(means)
    mean_valid = sum(weights) / len(weights)

    max_drop, drop_month = 0.0, None
    for prev, cur in zip(usable, usable[1:]):
        drop = prev.mean_ndvi - cur.mean_ndvi
        if drop > max_drop:
            max_drop, drop_month = drop, cur.month
    third = max(1, len(usable) // 3)
    decline = statistics.mean(means[:third]) - statistics.mean(means[-third:])
    disturbance = max_drop >= 0.25 or decline >= 0.25

    capacity = geom.area_ha * sat.sequestration_rate * canopy
    ratio = (claimed_tonnes / capacity) if capacity > 0 else math.inf

    # ── component scores (each 0..1) ──
    canopy_s = _clip((canopy - 0.20) / 0.60)
    ndvi_s = _clip((median_ndvi - 0.35) / 0.35)
    vegetation = 0.6 * canopy_s + 0.4 * ndvi_s
    stability = 1.0 if max_drop < 0.12 else _clip(1.0 - (max_drop - 0.12) / 0.18)
    plausibility = 1.0 if ratio <= 1.0 else _clip(1.0 - (ratio - 1.0) / 2.0)
    confidence = 0.5 * min(1.0, len(usable) / 8) + 0.5 * mean_valid
    if sat.low_confidence:
        confidence *= 0.5

    raw = 0.50 * vegetation + 0.20 * stability + 0.20 * plausibility + 0.10 * confidence
    score = round(100 * raw)

    caps: list[str] = []
    if sat.sequestration_rate <= 0:
        score, _ = min(score, 30), caps.append("non_forest_biome")
    if canopy < 0.40:
        score, _ = min(score, 45), caps.append("insufficient_canopy")
    if ratio > 3.0:
        score, _ = min(score, 55), caps.append("implausible_claim")
    if disturbance:
        score, _ = min(score, 40), caps.append("clearing_detected")
    if sat.low_confidence:
        score, _ = min(score, threshold - 1), caps.append("low_confidence_evidence")

    approved = score >= threshold
    verified = int(math.floor(min(claimed_tonnes, capacity))) if approved else 0
    if verified <= 0:
        approved, verified = False, 0

    checks = [
        Check("canopy", "Forest canopy cover",
              "pass" if canopy >= 0.6 else ("warn" if canopy >= 0.4 else "fail"),
              f"{canopy * 100:.0f}% of the site",
              "Share of observed pixels with NDVI of 0.5 or higher, weighted by cloud-free area."),
        Check("greenness", "Greenness (median NDVI)",
              "pass" if median_ndvi >= 0.55 else ("warn" if median_ndvi >= 0.40 else "fail"),
              f"{median_ndvi:.2f}", "Healthy dense forest is typically above 0.6."),
        Check("clearing", "No clearing detected during the year",
              "fail" if disturbance else "pass",
              (f"drop of {max_drop:.2f} in month {drop_month}" if disturbance else f"largest monthly drop {max_drop:.2f}"),
              "A sudden or sustained fall in NDVI suggests the trees were removed."),
        Check("biome", "Land can store forest carbon",
              "pass" if sat.sequestration_rate > 0 else "fail", sat.biome,
              f"Reference rate {sat.sequestration_rate:g} tCO2e per hectare per year."),
        Check("claim", "Claim fits what the land can hold",
              "pass" if ratio <= 1.0 else ("warn" if ratio <= 3.0 else "fail"),
              f"claimed {claimed_tonnes:,} t vs capacity {capacity:,.0f} t",
              "Credits are capped at capacity. Claims far above it fail." if ratio > 1.0 else "Within capacity."),
        Check("coverage", "Cloud-free observation coverage",
              "fail" if sat.low_confidence else ("pass" if len(usable) >= 6 else "warn"),
              f"{len(usable)} of 12 months usable",
              "More usable months give more reliable evidence."),
    ]

    metrics = {
        "area_ha": round(geom.area_ha, 2),
        "cells": len(geom.cells),
        "canopy_fraction": round(canopy, 4),
        "median_ndvi": round(median_ndvi, 4),
        "max_monthly_drop": round(max_drop, 4),
        "year_decline": round(decline, 4),
        "months_observed": len(usable),
        "mean_valid_fraction": round(mean_valid, 4),
        "claim_to_capacity_ratio": None if math.isinf(ratio) else round(ratio, 4),
        "sequestration_rate": sat.sequestration_rate,
    }
    components = {
        "vegetation": round(vegetation, 4), "stability": round(stability, 4),
        "claim_plausibility": round(plausibility, 4), "confidence": round(confidence, 4),
        "weights": {"vegetation": 0.50, "stability": 0.20, "claim_plausibility": 0.20, "confidence": 0.10},
    }
    return Assessment(score, approved, verified, round(capacity, 2), claimed_tonnes, checks, metrics, components, caps)
