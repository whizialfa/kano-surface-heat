from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MAPS = ROOT / "maps"
CHARTS = ROOT / "charts"
NOTES = ROOT / "notes"

SIBLING = ROOT.parent / "15-min-cities-nigeria" / "data" / "processed"
PORTFOLIO_DATA = ROOT.parents[1] / "Data"
AGESEX_DIR = PORTFOLIO_DATA / "NGA_population_v3_0_agesex"
POP_TOTAL = ROOT.parent / "15-min-cities-nigeria" / "data" / "raw" / "NGA_population_v3_0_gridded.tif"

BOUNDARY = DATA_PROCESSED / "kano_study_boundary.gpkg"
WARDS = DATA_PROCESSED / "kano_wards.gpkg"
HEXES = DATA_PROCESSED / "kano_hexes.gpkg"
SETTLEMENTS = DATA_PROCESSED / "kano_settlements.csv"
PLACES = DATA_PROCESSED / "kano_places.gpkg"

UTM = 32632
