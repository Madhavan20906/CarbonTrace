import dataclasses

import pytest

from app import geo
from app.satellite import Observation, SatelliteResult, SimulatedProvider
from app.scenarios import SCENARIOS, square
from app.scoring import assess


async def _run(scn):
    r = scn["request"]
    g = geo.analyse(r["polygon"])
    sat = await SimulatedProvider().observe(g, r["vintage"])
    return g, sat, assess(g, sat, r["claimed_tonnes"])


@pytest.mark.parametrize("scn", SCENARIOS, ids=lambda s: s["id"])
async def test_every_demo_scenario_behaves_as_documented(scn):
    g, sat, a = await _run(scn)
    expect = scn["expect"]
    if expect in ("approved", "chain-rejects"):
        assert a.approved and a.verified_tonnes == scn["request"]["claimed_tonnes"]
    elif expect == "approved-trimmed":
        assert a.approved and 0 < a.verified_tonnes < scn["request"]["claimed_tonnes"]
        assert a.verified_tonnes == int(a.capacity_tonnes)
    else:
        assert not a.approved and a.verified_tonnes == 0


async def test_clearing_hard_cap_applies():
    scn = next(s for s in SCENARIOS if s["id"] == "cleared-forest")
    _, _, a = await _run(scn)
    assert "clearing_detected" in a.caps_applied and a.score <= 40
    assert any(c.id == "clearing" and c.status == "fail" for c in a.checks)


async def test_scoring_is_deterministic():
    scn = SCENARIOS[0]
    _, _, a1 = await _run(scn)
    _, _, a2 = await _run(scn)
    assert a1.to_dict() == a2.to_dict()


async def test_huge_overclaim_is_rejected_not_trimmed():
    g = geo.analyse(square(11.65, 76.10, 1000))
    sat = await SimulatedProvider().observe(g, 2025)
    a = assess(g, sat, 1_000_000)
    assert not a.approved and a.verified_tonnes == 0


async def test_score_never_exceeds_100_or_goes_negative():
    for scn in SCENARIOS:
        _, _, a = await _run(scn)
        assert 0 <= a.score <= 100


def test_no_usable_observations_is_rejected():
    g = geo.analyse(square(11.65, 76.10, 900))
    obs = [Observation(m, 0.8, 0.7, 0.85, 0.9, 0.1) for m in range(1, 13)]  # all cloudy
    sat = SatelliteResult("sentinel2", False, "Tropical forest zone", 9.0, obs)
    a = assess(g, sat, 500)
    assert not a.approved and "no_observations" in a.caps_applied


async def test_low_confidence_evidence_can_never_approve():
    g = geo.analyse(square(11.65, 76.10, 900))
    sat = dataclasses.replace(await SimulatedProvider().observe(g, 2025), low_confidence=True)
    a = assess(g, sat, 300)
    assert not a.approved and "low_confidence_evidence" in a.caps_applied
