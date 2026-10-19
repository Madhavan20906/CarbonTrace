"""Preset demo scenarios for the Fraud Lab. Each one is a normal verify request the UI can replay."""
from __future__ import annotations

import math


def square(lat: float, lon: float, side_m: float, wobble: float = 0.0) -> list[list[float]]:
    """Closed [lon, lat] ring of an (optionally slightly irregular) square centred on lat/lon."""
    half_lat = side_m / 2 / 110_574.0
    half_lon = side_m / 2 / (111_320.0 * math.cos(math.radians(lat)))
    w = wobble
    ring = [
        [lon - half_lon, lat - half_lat],
        [lon + half_lon * (1 + w), lat - half_lat * (1 - w)],
        [lon + half_lon, lat + half_lat * (1 + w)],
        [lon - half_lon * (1 - w), lat + half_lat],
    ]
    ring.append(ring[0])
    return ring


WAYANAD = square(11.652, 76.105, 1100, 0.04)  # about 120 ha of Western Ghats rainforest
OREGON = square(44.80, -123.60, 1500, 0.03)  # about 225 ha of coastal conifer forest
BORNEO = square(0.80, 114.00, 900, 0.03)  # about 80 ha of Bornean rainforest

SCENARIOS = [
    {
        "id": "legit-wayanad",
        "title": "Rainforest restoration, Western Ghats",
        "story": "A genuine, well-documented forest. This should pass and mint credits.",
        "expect": "approved",
        "request": {"name": "Wayanad Rainforest Restoration", "vintage": 2025, "polygon": WAYANAD,
                    "claimed_tonnes": 700, "project_type": "reforestation"},
    },
    {
        "id": "double-count",
        "title": "Same land, claimed again",
        "story": "A second developer submits the exact same polygon. The AI says it is a real forest, "
                 "but the contract must refuse to mint it a second time.",
        "expect": "chain-rejects",
        "request": {"name": "Wayanad Carbon Partners (duplicate)", "vintage": 2025, "polygon": WAYANAD,
                    "claimed_tonnes": 700, "project_type": "reforestation"},
    },
    {
        "id": "fake-desert",
        "title": "A 'forest' in the Thar Desert",
        "story": "A glossy proposal for a forest where satellites see bare sand.",
        "expect": "rejected",
        "request": {"name": "Thar Green Wall Project", "vintage": 2025, "polygon": square(27.0, 71.0, 1200, 0.03),
                    "claimed_tonnes": 5000, "project_type": "reforestation"},
    },
    {
        "id": "fake-city",
        "title": "'Urban forest' in a dense city",
        "story": "Credits claimed for tree cover in the middle of built-up Chennai.",
        "expect": "rejected",
        "request": {"name": "Metro Canopy Credits", "vintage": 2025, "polygon": square(13.08, 80.27, 1000, 0.02),
                    "claimed_tonnes": 3000, "project_type": "conservation"},
    },
    {
        "id": "cleared-forest",
        "title": "Forest that was cut down mid-year",
        "story": "The land was forest in January and bare by July. The claim ignores that.",
        "expect": "rejected",
        "request": {"name": "Rondonia Conservation Parcel", "vintage": 2025, "polygon": square(-10.8, -63.0, 1300, 0.03),
                    "claimed_tonnes": 9000, "project_type": "conservation"},
    },
    {
        "id": "inflated-claim",
        "title": "Real forest, inflated numbers",
        "story": "Genuine forest, but the developer claims about twice what the land can hold. "
                 "The AI trims the credits down to capacity.",
        "expect": "approved-trimmed",
        "request": {"name": "Borneo Peat Forest Reserve", "vintage": 2025, "polygon": BORNEO,
                    "claimed_tonnes": 1500, "project_type": "conservation"},
    },
    {
        "id": "legit-oregon",
        "title": "Temperate conifer reforestation, Oregon",
        "story": "A second genuine project in a different biome.",
        "expect": "approved",
        "request": {"name": "Coast Range Conifer Recovery", "vintage": 2025, "polygon": OREGON,
                    "claimed_tonnes": 700, "project_type": "reforestation"},
    },
]
