import pytest

from app import geo
from app.scenarios import square


def test_square_area_is_close_to_expected():
    g = geo.analyse(square(11.65, 76.10, 1000))
    assert 95 < g.area_ha < 105  # 1 km x 1 km = 100 ha


def test_cells_are_strictly_ascending_and_unique():
    g = geo.analyse(square(44.8, -123.6, 1500, 0.03))
    assert g.cells == sorted(set(g.cells))
    assert 0 < len(g.cells) <= geo.MAX_CELLS


def test_accepts_geojson_polygon_and_bare_ring_equally():
    ring = square(11.65, 76.10, 800)
    assert geo.analyse([ring]).cells == geo.analyse(ring).cells


def test_open_ring_is_closed_automatically():
    ring = square(11.65, 76.10, 800)[:-1]
    assert geo.analyse(ring).ring[0] == geo.analyse(ring).ring[-1]


def test_bowtie_is_rejected():
    bowtie = [[0.0, 0.0], [0.01, 0.01], [0.01, 0.0], [0.0, 0.01], [0.0, 0.0]]
    with pytest.raises(geo.GeometryError, match="cross"):
        geo.analyse(bowtie)


def test_too_large_and_too_small_are_rejected():
    with pytest.raises(geo.GeometryError, match="too large"):
        geo.analyse(square(10, 10, 80_000))
    with pytest.raises(geo.GeometryError, match="too small"):
        geo.analyse(square(10, 10, 20))


def test_oversized_cell_count_is_rejected():
    with pytest.raises(geo.GeometryError, match="grid cells"):
        geo.analyse(square(0.0, 10.0, 7_500))  # ~5,600 ha -> well over 256 cells


@pytest.mark.parametrize("bad", [[], [[0, 0], [1, 1]], [[200, 0], [201, 0], [201, 1], [200, 0]], [["a", "b"]] * 4])
def test_malformed_input_is_rejected(bad):
    with pytest.raises(geo.GeometryError):
        geo.analyse(bad)


def test_cell_id_roundtrip():
    cid = geo.cell_id(11.6531, 76.1042)
    min_lon, min_lat, max_lon, max_lat = geo.cell_bounds(cid)
    assert min_lat <= 11.6531 < max_lat and min_lon <= 76.1042 < max_lon


def test_identical_polygons_share_identical_cells_and_shifted_ones_do_not_fully_overlap():
    a = geo.analyse(square(11.65, 76.10, 1000))
    b = geo.analyse(square(11.65, 76.10, 1000))
    far = geo.analyse(square(11.70, 76.10, 1000))
    assert a.cells == b.cells
    assert not set(a.cells) & set(far.cells)


def test_polygon_inside_one_cell_still_claims_one_cell():
    g = geo.analyse(square(11.65, 76.10, 90))  # ~0.8 ha, far smaller than one cell
    assert len(g.cells) == 1
