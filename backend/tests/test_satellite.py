import httpx
import numpy as np
import pytest

from app import geo
from app.scenarios import square
from app.satellite import Sentinel2Provider, SimulatedProvider, nearest_reference, ndvi_stats, rate_for_latitude


def test_ndvi_stats_dense_vegetation():
    red = np.full((10, 10), 500)  # reflectance 0.05
    nir = np.full((10, 10), 4000)  # reflectance 0.40
    scl = np.full((10, 10), 4)
    inside = np.ones((10, 10), bool)
    mean, p10, p90, canopy, valid = ndvi_stats(red, nir, scl, inside)
    assert 0.77 < mean < 0.79 and canopy == 1.0 and valid == 1.0


def test_ndvi_stats_masks_clouds_and_outside_pixels():
    red = np.full((4, 4), 500)
    nir = np.full((4, 4), 4000)
    scl = np.full((4, 4), 4)
    scl[:2, :] = 9  # cloud over half the scene
    inside = np.ones((4, 4), bool)
    inside[:, 3] = False  # last column is outside the polygon
    *_, valid = ndvi_stats(red, nir, scl, inside)
    assert valid == pytest.approx(6 / 12)


def test_ndvi_stats_returns_none_when_nothing_usable():
    z = np.full((3, 3), 500)
    assert ndvi_stats(z, z, np.full((3, 3), 9), np.ones((3, 3), bool)) is None
    assert ndvi_stats(z, z, np.full((3, 3), 4), np.zeros((3, 3), bool)) is None


def test_ndvi_stats_applies_baseline_offset():
    red, nir, scl = np.full((2, 2), 1500), np.full((2, 2), 5000), np.full((2, 2), 4)
    no_off = ndvi_stats(red, nir, scl, np.ones((2, 2), bool))[0]
    with_off = ndvi_stats(red, nir, scl, np.ones((2, 2), bool), offset=-0.1)[0]
    assert with_off > no_off


def test_reference_lookup():
    assert nearest_reference(11.65, 76.10).name.startswith("Western Ghats")
    assert nearest_reference(13.08, 80.27).kind == "urban"
    assert nearest_reference(27.0, 71.0).kind == "desert"
    assert nearest_reference(-45.0, 170.0) is None


async def test_simulated_is_deterministic_and_flagged():
    g = geo.analyse(square(11.65, 76.10, 900))
    a = await SimulatedProvider().observe(g, 2025)
    b = await SimulatedProvider().observe(g, 2025)
    c = await SimulatedProvider().observe(g, 2024)
    assert a.simulated and a.provider == "simulated"
    assert a.to_dict() == b.to_dict()
    assert a.to_dict() != c.to_dict()
    assert any("SIMULATED" in n for n in a.notes)
    assert len(a.observations) == 12


async def test_simulated_unknown_location_is_low_confidence():
    g = geo.analyse(square(-45.0, 170.0, 900))
    r = await SimulatedProvider().observe(g, 2025)
    assert r.low_confidence and r.reference is None


async def test_simulated_cleared_site_shows_ndvi_collapse():
    g = geo.analyse(square(-10.8, -63.0, 900))
    r = await SimulatedProvider().observe(g, 2025)
    by_month = {o.month: o.mean_ndvi for o in r.observations}
    assert by_month[2] > 0.7 and by_month[9] < 0.4


def test_rate_for_latitude_bands():
    assert rate_for_latitude(1)[1] > rate_for_latitude(45)[1] > rate_for_latitude(65)[1]


async def test_sentinel2_stac_search_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"features": [{"id": "S2A_TEST", "assets": {}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        items = await Sentinel2Provider()._search(client, (76.0, 11.6, 76.1, 11.7), 2025, 12)
    assert items[0]["id"] == "S2A_TEST"
    assert "sentinel-2-l2a" in seen["body"] and "2025-12-01T00:00:00Z/2026-01-01T00:00:00Z" in seen["body"]
