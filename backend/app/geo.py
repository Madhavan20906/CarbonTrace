"""Polygon validation, area computation and rasterisation into on-chain grid cells.

Grid: cell id = (latIdx << 32) | lonIdx where idx = floor((deg + offset) * 1e6 / CELL_SIZE_MICRODEG).
This MUST stay in sync with CELL_SIZE_MICRODEG in CarbonTraceRegistry.sol.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import Polygon, box

CELL_SIZE_MICRODEG = 2000
CELL_DEG = CELL_SIZE_MICRODEG / 1_000_000
MAX_CELLS = 256
MIN_AREA_HA = 0.5
MAX_BBOX_SPAN_DEG = 0.5
MIN_CELL_COVERAGE = 0.20  # a cell is part of the claim if the polygon covers >= 20% of it

METERS_PER_DEG_LAT = 110_574.0
METERS_PER_DEG_LON_EQ = 111_320.0


class GeometryError(ValueError):
    """Raised with a user-readable message when a polygon cannot be used."""


@dataclass(frozen=True)
class Geometry:
    ring: list[tuple[float, float]]  # (lon, lat), closed
    area_ha: float
    centroid_lat: float
    centroid_lon: float
    cells: list[int]  # strictly ascending
    bbox: tuple[float, float, float, float]  # minLon, minLat, maxLon, maxLat

    @property
    def centroid_lat_e6(self) -> int:
        return round(self.centroid_lat * 1_000_000)

    @property
    def centroid_lon_e6(self) -> int:
        return round(self.centroid_lon * 1_000_000)


def cell_id(lat: float, lon: float) -> int:
    lat_idx = math.floor((lat + 90.0) / CELL_DEG)
    lon_idx = math.floor((lon + 180.0) / CELL_DEG)
    return (lat_idx << 32) | lon_idx


def cell_bounds(cid: int) -> tuple[float, float, float, float]:
    """(minLon, minLat, maxLon, maxLat) of a cell."""
    lat_idx, lon_idx = cid >> 32, cid & 0xFFFFFFFF
    min_lat = lat_idx * CELL_DEG - 90.0
    min_lon = lon_idx * CELL_DEG - 180.0
    return (min_lon, min_lat, min_lon + CELL_DEG, min_lat + CELL_DEG)


def parse_ring(coords: list) -> list[tuple[float, float]]:
    """Accepts GeoJSON Polygon coordinates ([[ [lon,lat], ... ]]) or a bare ring ([ [lon,lat], ... ])."""
    if not coords:
        raise GeometryError("Polygon is empty.")
    ring = coords[0] if isinstance(coords[0][0], (list, tuple)) else coords
    try:
        pts = [(float(p[0]), float(p[1])) for p in ring]
    except (TypeError, ValueError, IndexError) as e:
        raise GeometryError("Polygon coordinates must be [longitude, latitude] pairs.") from e
    if pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    if len(pts) < 4:
        raise GeometryError("A polygon needs at least 3 distinct corners.")
    for lon, lat in pts:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise GeometryError("Coordinates out of range: longitude must be -180..180 and latitude -90..90.")
    return pts


def _to_meters(pts: list[tuple[float, float]], lat0: float, lon0: float) -> list[tuple[float, float]]:
    k = METERS_PER_DEG_LON_EQ * math.cos(math.radians(lat0))
    return [((lon - lon0) * k, (lat - lat0) * METERS_PER_DEG_LAT) for lon, lat in pts]


def analyse(coords: list) -> Geometry:
    ring = parse_ring(coords)
    poly = Polygon(ring)
    if not poly.is_valid:
        raise GeometryError("Polygon is invalid (edges cross each other). Redraw it without self-intersections.")

    min_lon, min_lat, max_lon, max_lat = poly.bounds
    if (max_lon - min_lon) > MAX_BBOX_SPAN_DEG or (max_lat - min_lat) > MAX_BBOX_SPAN_DEG:
        raise GeometryError("Polygon is too large. Split the project into smaller sites.")

    c = poly.centroid
    lat0, lon0 = c.y, c.x
    area_m2 = Polygon(_to_meters(ring, lat0, lon0)).area
    area_ha = area_m2 / 10_000.0
    if area_ha < MIN_AREA_HA:
        raise GeometryError(f"Polygon is too small ({area_ha:.2f} ha). Minimum is {MIN_AREA_HA} ha.")

    cells = _rasterise(poly, lat0, lon0)
    if len(cells) > MAX_CELLS:
        raise GeometryError(
            f"Polygon covers {len(cells)} grid cells; the registry accepts at most {MAX_CELLS} per project. "
            "Split the project into smaller sites."
        )
    return Geometry(ring=ring, area_ha=area_ha, centroid_lat=lat0, centroid_lon=lon0, cells=cells,
                    bbox=(min_lon, min_lat, max_lon, max_lat))


def _rasterise(poly: Polygon, lat0: float, lon0: float) -> list[int]:
    min_lon, min_lat, max_lon, max_lat = poly.bounds
    lat_lo, lat_hi = math.floor((min_lat + 90.0) / CELL_DEG), math.floor((max_lat + 90.0) / CELL_DEG)
    lon_lo, lon_hi = math.floor((min_lon + 180.0) / CELL_DEG), math.floor((max_lon + 180.0) / CELL_DEG)
    cell_area = CELL_DEG * CELL_DEG
    out: set[int] = set()
    for la in range(lat_lo, lat_hi + 1):
        for lo in range(lon_lo, lon_hi + 1):
            cid = (la << 32) | lo
            b = cell_bounds(cid)
            inter = poly.intersection(box(*b))
            if not inter.is_empty and inter.area / cell_area >= MIN_CELL_COVERAGE:
                out.add(cid)
    if not out:  # tiny polygon inside one cell: claim the cell holding its centroid
        out.add(cell_id(lat0, lon0))
    return sorted(out)
