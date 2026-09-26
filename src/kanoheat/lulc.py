"""Land cover for the plate: most common WorldCover class in each 30 m cell, as polygons.

The 30 m cells are the Landsat surface-temperature cells, so the plate shows the
same unit the composition analysis uses.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape

from . import timing
from .composition import WORLDCOVER, inside_mask
from .lst import PIXEL, grid
from .paths import DATA_PROCESSED, UTM

LULC_GPKG = DATA_PROCESSED / "kano_lulc_30m.gpkg"
SHARES_CSV = DATA_PROCESSED / "lulc_shares.csv"

# WorldCover code → (plate order, label)
CLASSES = {
    50: (1, "Built-up"),
    40: (2, "Cropland"),
    60: (3, "Bare ground"),
    30: (4, "Grass"),
    20: (5, "Shrubs"),
    10: (6, "Trees"),
    90: (7, "Water and wetland"),
    80: (7, "Water and wetland"),
}


def modal_30m() -> np.ndarray:
    with rasterio.open(WORLDCOVER) as src:
        wc = src.read(1)
    _, width, height = grid()
    blocks = wc[: height * 3, : width * 3].reshape(height, 3, width, 3).transpose(0, 2, 1, 3).reshape(height, width, 9)
    codes = np.array(sorted(CLASSES))
    counts = np.stack([(blocks == c).sum(axis=2) for c in codes], axis=-1)
    out = codes[counts.argmax(axis=-1)].astype("uint8")
    out[counts.sum(axis=-1) == 0] = 0
    return out


def build() -> gpd.GeoDataFrame:
    modal = modal_30m()
    inside = inside_mask()
    modal[~inside] = 0
    transform, _, _ = grid()
    feats = [
        {"geometry": shape(geom), "wc": int(val)}
        for geom, val in shapes(modal, mask=modal > 0, transform=transform, connectivity=4)
    ]
    gdf = gpd.GeoDataFrame(feats, crs=UTM)
    gdf["code"] = gdf["wc"].map(lambda c: CLASSES[c][0]).astype("int16")
    gdf["cover"] = gdf["wc"].map(lambda c: CLASSES[c][1])
    gdf.to_crs(4326).to_file(LULC_GPKG, layer="kano_lulc_30m", driver="GPKG")

    n = inside.sum()
    rows = []
    labels = {}
    for wc_code, (order, label) in CLASSES.items():
        labels.setdefault((order, label), []).append(wc_code)
    for (order, label), codes in sorted(labels.items()):
        cells = int((np.isin(modal, codes) & inside).sum())
        rows.append({"order": order, "cover": label, "worldcover": "+".join(map(str, sorted(codes))),
                     "cells_30m": cells, "km2": round(cells * PIXEL * PIXEL / 1e6, 1), "share": round(cells / n, 4)})
    pd.DataFrame(rows).to_csv(SHARES_CSV, index=False)
    return gdf


def main() -> None:
    t0 = timing.start("LULC plate layer", "modal WorldCover per 30 m cell, polygonised")
    gdf = build()
    timing.done("LULC plate layer", t0, f"{len(gdf):,} polygons → {LULC_GPKG.name}")
    print(pd.read_csv(SHARES_CSV).to_string(index=False))


if __name__ == "__main__":
    main()
