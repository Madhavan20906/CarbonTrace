"""Satellite evidence providers.

Two interchangeable providers return the same `SatelliteResult`:

* `SimulatedProvider`  (default)  deterministic, offline, biome-reference demo data. It is NOT satellite
  data and every result is flagged `simulated=True` so it can never be mistaken for real evidence.
* `Sentinel2Provider`  live Sentinel-2 L2A NDVI computed from public Cloud-Optimised GeoTIFFs found via the
  Element84 Earth Search STAC API (no API key required). Needs `pip install -r requirements-live.txt`.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
from dataclasses import asdict, dataclass, field
from typing import Protocol

import numpy as np

from .geo import Geometry


class ProviderUnavailable(RuntimeError):
    pass


@dataclass
class Observation:
    month: int
    mean_ndvi: float
    p10: float
    p90: float
    canopy_fraction: float  # share of valid pixels with NDVI >= 0.5
    valid_fraction: float  # share of the polygon with a usable (cloud-free) observation
    scene_id: str | None = None


@dataclass
class SatelliteResult:
    provider: str
    simulated: bool
    biome: str
    sequestration_rate: float  # conservative tCO2e per hectare per year for this biome
    observations: list[Observation]
    low_confidence: bool = False
    reference: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class SatelliteProvider(Protocol):
    async def observe(self, geom: Geometry, vintage: int) -> SatelliteResult: ...


# ─────────────────────────── Simulated provider ───────────────────────────

@dataclass(frozen=True)
class Reference:
    name: str
    lat: float
    lon: float
    radius_km: float
    kind: str  # forest_evergreen | forest_temperate | cropland | desert | urban | cleared
    base: float
    amp: float
    biome: str
    rate: float
    peak_month: int = 7
    clearing_month: int | None = None
    cleared_ndvi: float = 0.27


REFERENCES: tuple[Reference, ...] = (
    Reference("Western Ghats, India", 11.65, 76.10, 120, "forest_evergreen", 0.80, 0.05, "Tropical moist forest", 9.0, 10),
    Reference("Central Amazon, Brazil", -3.4, -60.0, 900, "forest_evergreen", 0.84, 0.04, "Tropical moist forest", 10.0, 4),
    Reference("Borneo, Indonesia", 0.8, 114.0, 500, "forest_evergreen", 0.83, 0.04, "Tropical moist forest", 10.0, 3),
    Reference("Congo Basin", 0.2, 23.0, 800, "forest_evergreen", 0.83, 0.04, "Tropical moist forest", 9.5, 3),
    Reference("Oregon Coast Range, USA", 44.8, -123.6, 400, "forest_temperate", 0.72, 0.10, "Temperate conifer forest", 6.0, 7),
    Reference("Thar Desert, India", 27.0, 71.0, 350, "desert", 0.09, 0.03, "Arid desert", 0.0, 8),
    Reference("Sahara, Africa", 23.0, 12.0, 1500, "desert", 0.06, 0.02, "Arid desert", 0.0, 8),
    Reference("Arabian Desert", 23.5, 46.0, 800, "desert", 0.05, 0.02, "Arid desert", 0.0, 3),
    Reference("Chennai urban area, India", 13.08, 80.27, 40, "urban", 0.22, 0.06, "Urban / built-up", 0.0, 11),
    Reference("Mumbai urban area, India", 19.08, 72.88, 40, "urban", 0.24, 0.06, "Urban / built-up", 0.0, 9),
    Reference("Punjab croplands, India", 30.9, 75.6, 200, "cropland", 0.45, 0.30, "Annual cropland", 0.0, 2),
    Reference("Rondonia arc of deforestation, Brazil", -10.8, -63.0, 150, "cleared", 0.82, 0.03, "Tropical moist forest", 10.0, 3, clearing_month=6),
)

_SPREAD = {"forest_evergreen": 0.05, "forest_temperate": 0.07, "cropland": 0.12, "desert": 0.03, "urban": 0.15, "cleared": 0.06}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def nearest_reference(lat: float, lon: float) -> Reference | None:
    best: tuple[float, Reference] | None = None
    for ref in REFERENCES:
        ratio = _haversine_km(lat, lon, ref.lat, ref.lon) / ref.radius_km
        if ratio <= 1.0 and (best is None or ratio < best[0]):
            best = (ratio, ref)
    return best[1] if best else None


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class SimulatedProvider:
    """Deterministic biome-based NDVI series. Same polygon + vintage always yields the same series."""

    name = "simulated"

    async def observe(self, geom: Geometry, vintage: int) -> SatelliteResult:
        seed_src = ",".join(map(str, geom.cells)) + f"|{vintage}"
        seed = int.from_bytes(hashlib.sha256(seed_src.encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        ref = nearest_reference(geom.centroid_lat, geom.centroid_lon)

        notes = [
            "SIMULATED DATA: values come from a coarse biome reference table, not from satellite observations.",
            "Set SATELLITE_PROVIDER=sentinel2 to compute NDVI from real Sentinel-2 imagery.",
        ]
        if ref is None:
            ref_unknown = Reference("Unknown", geom.centroid_lat, geom.centroid_lon, 1, "forest_temperate", 0.45, 0.08, "Unclassified land", 3.0, 7)
            notes.append("No biome reference near this location; evidence is low confidence.")
            return self._series(ref_unknown, rng, vintage, low_confidence=True, notes=notes, reference=None)
        notes.append(f"Reference site: {ref.name}.")
        return self._series(ref, rng, vintage, low_confidence=False, notes=notes, reference=ref.name)

    def _series(self, ref: Reference, rng: np.random.Generator, vintage: int, *, low_confidence: bool,
                notes: list[str], reference: str | None) -> SatelliteResult:
        site_offset = float(rng.normal(0, 0.015))  # per-polygon heterogeneity
        spread = _SPREAD.get(ref.kind, 0.07)
        obs: list[Observation] = []
        for m in range(1, 13):
            if ref.kind == "cropland":
                seasonal = math.sin(2 * math.pi * 2 * (m - ref.peak_month) / 12 + math.pi / 2)
            else:
                seasonal = math.cos(2 * math.pi * (m - ref.peak_month) / 12)
            mean = ref.base + ref.amp * seasonal * 0.5 + site_offset + float(rng.normal(0, 0.012))
            if ref.kind == "cleared" and ref.clearing_month and m >= ref.clearing_month:
                mean = ref.cleared_ndvi + float(rng.normal(0, 0.02))
            mean = float(np.clip(mean, -0.05, 0.95))
            wet = m in (6, 7, 8, 9) and ref.kind == "forest_evergreen"
            valid = float(rng.uniform(0.35, 0.7) if wet else rng.uniform(0.6, 0.98))
            canopy = float(np.clip(_logistic((mean - 0.5) / 0.07) + rng.normal(0, 0.01), 0.0, 1.0))
            obs.append(Observation(
                month=m,
                mean_ndvi=round(mean, 4),
                p10=round(float(np.clip(mean - spread, -0.1, 0.95)), 4),
                p90=round(float(np.clip(mean + spread, -0.1, 0.98)), 4),
                canopy_fraction=round(canopy, 4),
                valid_fraction=round(valid, 4),
                scene_id=f"SIM-{vintage}-{m:02d}",
            ))
        return SatelliteResult("simulated", True, ref.biome, ref.rate, obs, low_confidence, reference, notes)


# ─────────────────────────── Live Sentinel-2 provider ───────────────────────────

_VALID_SCL = {4, 5, 6, 7}  # vegetation, bare soil, water, unclassified. Excludes cloud, shadow, snow, no-data.


def ndvi_stats(red: np.ndarray, nir: np.ndarray, scl: np.ndarray, inside: np.ndarray, *, offset: float = 0.0,
               scale: float = 0.0001) -> tuple[float, float, float, float, float] | None:
    """Pure NDVI statistics for one scene window.

    Returns (mean, p10, p90, canopy_fraction, valid_fraction) or None when nothing in the polygon is usable.
    `inside` is True for pixels inside the polygon.
    """
    if inside.sum() == 0:
        return None
    r = red.astype("float32") * scale + offset
    n = nir.astype("float32") * scale + offset
    valid = inside & np.isin(scl, list(_VALID_SCL)) & (red > 0) & (nir > 0)
    if valid.sum() == 0:
        return None
    ndvi = (n[valid] - r[valid]) / (n[valid] + r[valid] + 1e-9)
    ndvi = np.clip(ndvi, -1.0, 1.0)
    return (
        float(ndvi.mean()),
        float(np.percentile(ndvi, 10)),
        float(np.percentile(ndvi, 90)),
        float((ndvi >= 0.5).mean()),
        float(valid.sum() / inside.sum()),
    )


def rate_for_latitude(lat: float) -> tuple[str, float]:
    """Conservative placeholder sequestration rates (tCO2e/ha/yr). Replace with an approved methodology
    (e.g. Verra VM0047 / Gold Standard) before issuing real credits."""
    a = abs(lat)
    if a < 10:
        return "Tropical forest zone", 9.0
    if a < 25:
        return "Subtropical forest zone", 7.0
    if a < 40:
        return "Warm temperate forest zone", 5.5
    if a < 55:
        return "Temperate forest zone", 4.5
    return "Boreal forest zone", 2.5


class Sentinel2Provider:
    name = "sentinel2"
    STAC_URL = "https://earth-search.aws.element84.com/v1/search"

    def __init__(self, max_cloud: float = 40.0, scenes_per_month: int = 3, http_timeout: float = 30.0):
        self.max_cloud = max_cloud
        self.scenes_per_month = scenes_per_month
        self.http_timeout = http_timeout

    async def observe(self, geom: Geometry, vintage: int) -> SatelliteResult:
        try:
            import rasterio  # noqa: F401
        except ImportError as e:  # pragma: no cover
            raise ProviderUnavailable("Live mode needs `pip install -r requirements-live.txt`.") from e
        import httpx

        loop = asyncio.get_running_loop()
        observations: list[Observation] = []
        async with httpx.AsyncClient(timeout=self.http_timeout) as client:
            for month in range(1, 13):
                items = await self._search(client, geom.bbox, vintage, month)
                best: Observation | None = None
                for item in items[: self.scenes_per_month]:
                    stats = await loop.run_in_executor(None, self._read_scene, item, geom)
                    if stats is None:
                        continue
                    mean, p10, p90, canopy, valid = stats
                    cand = Observation(month, round(mean, 4), round(p10, 4), round(p90, 4), round(canopy, 4),
                                       round(valid, 4), item.get("id"))
                    if best is None or cand.valid_fraction > best.valid_fraction:
                        best = cand
                    if cand.valid_fraction >= 0.8:
                        break
                if best:
                    observations.append(best)
        biome, rate = rate_for_latitude(geom.centroid_lat)
        notes = ["Live Sentinel-2 L2A imagery via Earth Search STAC; NDVI = (NIR-Red)/(NIR+Red), cloud-masked with SCL."]
        if len(observations) < 4:
            notes.append("Fewer than 4 usable monthly observations; evidence is low confidence.")
        return SatelliteResult("sentinel2", False, biome, rate, observations, low_confidence=len(observations) < 4,
                               reference=None, notes=notes)

    async def _search(self, client, bbox, vintage: int, month: int) -> list[dict]:
        end_year, end_month = (vintage + 1, 1) if month == 12 else (vintage, month + 1)
        body = {
            "collections": ["sentinel-2-l2a"],
            "bbox": list(bbox),
            "datetime": f"{vintage}-{month:02d}-01T00:00:00Z/{end_year}-{end_month:02d}-01T00:00:00Z",
            "query": {"eo:cloud_cover": {"lt": self.max_cloud}},
            "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
            "limit": 6,
        }
        resp = await client.post(self.STAC_URL, json=body)
        resp.raise_for_status()
        return resp.json().get("features", [])

    @staticmethod
    def _read_scene(item: dict, geom: Geometry):  # pragma: no cover - needs network + GDAL
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.features import geometry_mask  # noqa: F401
        from rasterio.mask import raster_geometry_mask
        from rasterio.warp import transform_geom
        from rasterio.windows import bounds as win_bounds
        from rasterio.windows import from_bounds

        assets = item["assets"]
        shape = {"type": "Polygon", "coordinates": [[list(p) for p in geom.ring]]}
        env = dict(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                   CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF")
        try:
            with rasterio.Env(**env):
                with rasterio.open(assets["red"]["href"]) as red_ds:
                    g = transform_geom("EPSG:4326", red_ds.crs, shape)
                    outside, _, window = raster_geometry_mask(red_ds, [g], crop=True, all_touched=True)
                    red = red_ds.read(1, window=window)
                    bounds = win_bounds(window, red_ds.transform)
                    bands = assets["red"].get("raster:bands", [{}])
                    scale = float(bands[0].get("scale", 0.0001))
                    offset = float(bands[0].get("offset", 0.0))
                with rasterio.open(assets["nir"]["href"]) as nir_ds:
                    nir = nir_ds.read(1, window=window)
                with rasterio.open(assets["scl"]["href"]) as scl_ds:
                    win = from_bounds(*bounds, transform=scl_ds.transform)
                    scl = scl_ds.read(1, window=win, out_shape=red.shape, resampling=Resampling.nearest)
        except Exception:
            return None
        return ndvi_stats(red, nir, scl, ~outside, offset=offset, scale=scale)


def get_provider(name: str) -> SatelliteProvider:
    if name == "sentinel2":
        return Sentinel2Provider()
    if name == "simulated":
        return SimulatedProvider()
    raise ValueError(f"Unknown SATELLITE_PROVIDER '{name}' (use 'simulated' or 'sentinel2').")
