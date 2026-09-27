"""Per-season median land surface temperature from Landsat C2 L2 ST_B10.

Every scene is warped onto one fixed 30 m UTM grid covering the study outline
plus a rural ring, so medians are taken pixel by pixel on the same cells.
"""

from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer as pc
import rasterio
import rasterio.errors
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT

from . import timing
from .paths import BOUNDARY, DATA_RAW, UTM
from .scenes import COLLECTION, GDAL_ENV, QA_BAD, QA_FILL, STAC, usable

RING_M = 10_000
PIXEL = 30.0
ST_SCALE = 0.00341802
ST_OFFSET = 149.0
LST_DIR = DATA_RAW / "lst"


def grid(ring_m: float = RING_M):
    outline = gpd.read_file(BOUNDARY).to_crs(UTM)
    xmin, ymin, xmax, ymax = outline.buffer(ring_m).total_bounds
    xmin = np.floor(xmin / PIXEL) * PIXEL
    ymin = np.floor(ymin / PIXEL) * PIXEL
    xmax = np.ceil(xmax / PIXEL) * PIXEL
    ymax = np.ceil(ymax / PIXEL) * PIXEL
    width = int((xmax - xmin) / PIXEL)
    height = int((ymax - ymin) / PIXEL)
    return from_origin(xmin, ymax, PIXEL, PIXEL), width, height


def _read(href: str, transform, width: int, height: int, dtype, nodata, *, tries: int = 4) -> np.ndarray:
    for attempt in range(1, tries + 1):
        try:
            with rasterio.Env(**GDAL_ENV):
                with rasterio.open(pc.sign(href)) as src:
                    with WarpedVRT(src, crs=f"EPSG:{UTM}", transform=transform, width=width, height=height,
                                   resampling=Resampling.nearest, src_nodata=nodata, nodata=nodata) as vrt:
                        return vrt.read(1, out_dtype=dtype)
        except rasterio.errors.RasterioIOError:
            if attempt == tries:
                raise
            time.sleep(5 * attempt)


def scene_lst(item, transform, width, height) -> np.ndarray:
    st = _read(item.assets["lwir11"].href, transform, width, height, "uint16", 0)
    qa = _read(item.assets["qa_pixel"].href, transform, width, height, "uint16", QA_FILL)
    ok = (st > 0) & ((qa & QA_FILL) == 0) & ((qa & QA_BAD) == 0)
    out = np.full(st.shape, np.nan, dtype="float32")
    out[ok] = st[ok].astype("float32") * ST_SCALE + ST_OFFSET - 273.15
    return out


def items_by_id(ids: list[str]):
    cat = Client.open(STAC, modifier=pc.sign_inplace)
    found = {}
    for k in range(0, len(ids), 50):
        chunk = ids[k:k + 50]
        for it in cat.search(collections=[COLLECTION], ids=chunk).items():
            found[it.id] = it
    return [found[i] for i in ids if i in found]


def season_median(season: str, year: int, *, min_clear: float = 0.98, workers: int = 6) -> tuple[np.ndarray, list[str]]:
    df = usable(min_clear=min_clear)
    pick = df[(df["season"] == season) & (df["year"] == year)].sort_values("date")
    ids = pick["id"].tolist()
    if not ids:
        raise ValueError(f"no usable {season} scenes in {year}")
    transform, width, height = grid()
    items = items_by_id(ids)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        stack = list(pool.map(lambda it: scene_lst(it, transform, width, height), items))
    arr = np.nanmedian(np.stack(stack), axis=0).astype("float32")
    return arr, ids


def write(arr: np.ndarray, name: str) -> str:
    LST_DIR.mkdir(parents=True, exist_ok=True)
    transform, width, height = grid()
    out = LST_DIR / f"{name}.tif"
    with rasterio.open(out, "w", driver="GTiff", width=width, height=height, count=1, dtype="float32",
                       crs=f"EPSG:{UTM}", transform=transform, nodata=np.nan, compress="deflate",
                       tiled=True, blockxsize=256, blockysize=256) as dst:
        dst.write(arr, 1)
    return str(out)


def build(season: str, years: list[int]) -> pd.DataFrame:
    rows = []
    for yr in years:
        t0 = timing.start(f"LST {season} {yr}")
        try:
            arr, ids = season_median(season, yr)
        except ValueError as exc:
            timing.done(f"LST {season} {yr}", t0, str(exc))
            continue
        path = write(arr, f"lst_{season}_{yr}")
        rows.append({"season": season, "year": yr, "scenes": len(ids), "path": path,
                     "ids": ";".join(ids)})
        timing.done(f"LST {season} {yr}", t0, f"{len(ids)} scenes → {path.split('/')[-1]}")
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="hot")
    ap.add_argument("--years", default="2026")
    args = ap.parse_args()
    years = [int(y) for y in args.years.split(",")] if "-" not in args.years else \
        list(range(int(args.years.split("-")[0]), int(args.years.split("-")[1]) + 1))
    print(build(args.season, years).drop(columns="ids").to_string(index=False))


if __name__ == "__main__":
    main()
