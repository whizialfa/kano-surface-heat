"""Landsat 8/9 Collection 2 Level-2 scenes over the Kano study outline.

Scene-level eo:cloud_cover describes the whole 185 km footprint, not the city.
Every candidate is scored on how much of the outline it covers and how much of
that is clear in QA_PIXEL.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer as pc
import rasterio
from pystac_client import Client
from rasterio.mask import mask
from shapely.geometry import shape

from . import timing
from .paths import BOUNDARY, DATA_PROCESSED, UTM

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"
PLATFORMS = ("landsat-8", "landsat-9")
INVENTORY = DATA_PROCESSED / "scene_inventory.csv"

QA_FILL = 1 << 0
QA_BAD = (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)

SEASON = {
    11: "harmattan", 12: "harmattan", 1: "harmattan", 2: "harmattan",
    3: "hot", 4: "hot", 5: "hot",
    6: "wet", 7: "wet", 8: "wet", 9: "wet",
    10: "transition",
}

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF",
    GDAL_HTTP_MAX_RETRY="4",
    GDAL_HTTP_RETRY_DELAY="2",
    GDAL_HTTP_TIMEOUT="60",
    GDAL_HTTP_CONNECTTIMEOUT="20",
)


def boundary() -> gpd.GeoDataFrame:
    return gpd.read_file(BOUNDARY).to_crs(4326)


def search(start: str = "2013-04-01", end: str = "2026-12-31"):
    outline = boundary()
    cat = Client.open(STAC, modifier=pc.sign_inplace)
    items = cat.search(
        collections=[COLLECTION],
        bbox=list(outline.total_bounds),
        datetime=f"{start}/{end}",
    ).item_collection()
    return [it for it in items if it.properties.get("platform") in PLATFORMS]


def _coverage(item, outline_utm) -> float:
    foot = gpd.GeoSeries([shape(item.geometry)], crs=4326).to_crs(UTM).iloc[0]
    geom = outline_utm.union_all()
    return float(foot.intersection(geom).area / geom.area)


def clear_fraction(item, outline: gpd.GeoDataFrame) -> tuple[float, int]:
    href = pc.sign(item.assets["qa_pixel"].href)
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(href) as src:
            shapes = outline.to_crs(src.crs).geometry
            arr, _ = mask(src, shapes, crop=True, filled=True, nodata=QA_FILL)
    qa = arr[0]
    inside = (qa & QA_FILL) == 0
    n = int(inside.sum())
    if n == 0:
        return 0.0, 0
    clear = inside & ((qa & QA_BAD) == 0)
    return float(clear.sum() / n), n


def inventory(*, with_qa: bool = True, min_cover: float = 0.98, max_scene_cloud: float = 40.0,
              workers: int = 8) -> pd.DataFrame:
    outline = boundary()
    outline_utm = outline.to_crs(UTM)
    items = search()
    rows = []
    for it in items:
        p = it.properties
        rows.append({
            "id": it.id,
            "date": p["datetime"][:10],
            "platform": p["platform"],
            "path_row": f'{p.get("landsat:wrs_path")}/{p.get("landsat:wrs_row")}',
            "scene_cloud": p.get("eo:cloud_cover"),
            "sun_elevation": p.get("view:sun_elevation"),
            "coverage": round(_coverage(it, outline_utm), 4),
        })
    df = pd.DataFrame(rows).drop_duplicates("id").sort_values("date").reset_index(drop=True)
    df["month"] = pd.to_datetime(df["date"]).dt.month
    df["year"] = pd.to_datetime(df["date"]).dt.year
    df["season"] = df["month"].map(SEASON)
    df["city_clear"] = np.nan
    df["city_pixels"] = np.nan

    if with_qa:
        by_id = {it.id: it for it in items}
        todo = df[(df["coverage"] >= min_cover) & (df["scene_cloud"] <= max_scene_cloud)]
        print(f"QA over {len(todo)} of {len(df)} scenes (coverage >= {min_cover}, scene cloud <= {max_scene_cloud}%)",
              flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(clear_fraction, by_id[sid], outline): sid for sid in todo["id"]}
            for k, fut in enumerate(as_completed(futures), 1):
                sid = futures[fut]
                try:
                    frac, n = fut.result()
                except Exception as exc:
                    print(f"  {sid} QA failed: {exc}", flush=True)
                    continue
                df.loc[df["id"] == sid, ["city_clear", "city_pixels"]] = [round(frac, 4), n]
                if k % 25 == 0:
                    print(f"  {k}/{len(todo)}", flush=True)

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(INVENTORY, index=False)
    return df


def usable(df: pd.DataFrame | None = None, *, min_clear: float = 0.98, min_cover: float = 0.98) -> pd.DataFrame:
    if df is None:
        df = pd.read_csv(INVENTORY)
    return df[(df["coverage"] >= min_cover) & (df["city_clear"] >= min_clear)].copy()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-qa", action="store_true")
    args = ap.parse_args()
    t0 = timing.start("scene inventory", "Landsat 8/9 C2 L2 over the Kano outline")
    df = inventory(with_qa=not args.no_qa)
    ok = usable(df) if not args.no_qa else df[df["coverage"] >= 0.98]
    summary = ok.groupby(["season"]).size().to_dict()
    timing.done("scene inventory", t0, f"{len(df)} scenes, {len(ok)} usable; by season {summary}")
    print(df["coverage"].describe().round(3).to_string())
    print(df.groupby("path_row")["coverage"].median().round(3).to_string())


if __name__ == "__main__":
    main()
