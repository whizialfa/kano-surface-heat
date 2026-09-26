"""Land-use mix inside each 30 m surface-temperature pixel (anchor table S2).

ESA WorldCover 10 m is warped onto a 10 m grid that nests exactly 3 x 3 inside
the 30 m LST grid, so every LST pixel holds nine land-use cells.
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer as pc
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT

from . import timing
from .lst import LST_DIR, PIXEL, grid
from .paths import BOUNDARY, DATA_PROCESSED, DATA_RAW, UTM
from .scenes import GDAL_ENV, STAC

WORLDCOVER = DATA_RAW / "worldcover_2021_10m.tif"
COMPOSITION_CSV = DATA_PROCESSED / "composition_lst.csv"
GRADIENT_CSV = DATA_PROCESSED / "composition_gradient.csv"

URBAN, BARE, VEG, WATER = 0, 1, 2, 3
GROUP_NAMES = ("urban", "bare", "vegetation", "water")

# WorldCover v200 codes: 10 tree, 20 shrub, 30 grass, 40 cropland, 50 built-up,
# 60 bare/sparse, 70 snow, 80 water, 90 wetland, 95 mangrove, 100 moss.
VARIANTS = {
    "anchor": {50: URBAN, 60: BARE, 10: VEG, 20: VEG, 30: VEG, 40: VEG, 95: VEG, 100: VEG, 80: WATER, 90: WATER},
    "sahel": {50: URBAN, 60: BARE, 40: BARE, 10: VEG, 20: VEG, 30: VEG, 95: VEG, 100: VEG, 80: WATER, 90: WATER},
}

CLASS_ORDER = ("C1", "C2", "C11", "C12", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10")
CLASS_CODE = {name: int(name[1:]) for name in CLASS_ORDER}
UNASSIGNED = 0
OUTSIDE = 255


def _between(x, lo=None, hi=None, lo_inc=False, hi_inc=False):
    ok = np.ones_like(x, dtype=bool)
    if lo is not None:
        ok &= (x >= lo) if lo_inc else (x > lo)
    if hi is not None:
        ok &= (x <= hi) if hi_inc else (x < hi)
    return ok


def rules(u, b, v, w, *, strict: bool = False):
    """Table S2 in percent of nine cells.

    Default reads a blank cell as unconstrained. Read as "none of that group"
    the table leaves 179 of the 220 possible nine-cell mixes unassigned, which
    cannot be how Bangalore was classified.
    """
    none = (lambda x: x == 0) if strict else (lambda x: np.ones_like(x, dtype=bool))
    return {
        "C1": b == 100,
        "C2": u == 100,
        "C11": v == 100,
        "C12": w == 100,
        "C3": _between(u, hi=45) & _between(b, 55, 90, lo_inc=True) & none(v) & none(w),
        "C4": _between(u, 55, 90, lo_inc=True) & _between(b, hi=45) & none(v) & none(w),
        "C5": _between(u, 50, 70) & _between(b, hi=20, hi_inc=True) & _between(v, hi=25) & none(w),
        "C6": _between(u, 35, 60) & _between(b, hi=35) & _between(v, hi=35) & none(w),
        "C7": _between(u, 30, 50) & _between(b, hi=20) & _between(v, 35, 60) & none(w),
        "C8": _between(u, 20, 40) & _between(b, hi=20) & _between(v, 40, 65) & _between(w, hi=15),
        "C9": _between(u, hi=25) & _between(b, hi=30) & _between(v, 45, 70) & _between(w, hi=25),
        "C10": _between(u, hi=25) & _between(b, hi=15) & _between(v, 50, 80) & _between(w, hi=25),
    }


def fetch_worldcover() -> str:
    transform30, width30, height30 = grid()
    t10 = Affine(PIXEL / 3, 0, transform30.c, 0, -PIXEL / 3, transform30.f)
    w10, h10 = width30 * 3, height30 * 3
    outline = gpd.read_file(BOUNDARY).to_crs(4326)
    cat = Client.open(STAC, modifier=pc.sign_inplace)
    items = [it for it in cat.search(collections=["esa-worldcover"], bbox=list(outline.buffer(0.2).total_bounds)).items()
             if "2021" in it.id]
    out = np.zeros((h10, w10), dtype="uint8")
    for it in items:
        with rasterio.Env(**GDAL_ENV):
            with rasterio.open(pc.sign(it.assets["map"].href)) as src:
                with WarpedVRT(src, crs=f"EPSG:{UTM}", transform=t10, width=w10, height=h10,
                               resampling=Resampling.nearest, src_nodata=0, nodata=0) as vrt:
                    part = vrt.read(1)
        out = np.where(out == 0, part, out)
    WORLDCOVER.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(WORLDCOVER, "w", driver="GTiff", width=w10, height=h10, count=1, dtype="uint8",
                       crs=f"EPSG:{UTM}", transform=t10, nodata=0, compress="deflate", tiled=True) as dst:
        dst.write(out, 1)
    return f"{len(items)} tiles → {WORLDCOVER.name}"


def group_counts(variant: str) -> np.ndarray:
    """(4, H30, W30) count of urban, bare, vegetation, water cells among the nine."""
    with rasterio.open(WORLDCOVER) as src:
        wc = src.read(1)
    lut = np.full(256, 255, dtype="uint8")
    for code, grp in VARIANTS[variant].items():
        lut[code] = grp
    g = lut[wc]
    h, w = g.shape[0] // 3, g.shape[1] // 3
    blocks = g[: h * 3, : w * 3].reshape(h, 3, w, 3)
    return np.stack([(blocks == k).sum(axis=(1, 3)) for k in range(4)]).astype("uint8")


def classify(counts: np.ndarray, *, strict: bool = False) -> np.ndarray:
    total = counts.sum(axis=0)
    pct = counts.astype("float32") / 9.0 * 100.0
    u, b, v, w = (np.round(pct[k], 4) for k in range(4))
    out = np.full(total.shape, UNASSIGNED, dtype="uint8")
    done = np.zeros(total.shape, dtype=bool)
    r = rules(u, b, v, w, strict=strict)
    for name in CLASS_ORDER:
        hit = r[name] & ~done
        out[hit] = CLASS_CODE[name]
        done |= hit
    out[total < 9] = OUTSIDE
    return out


def write_class(arr: np.ndarray, variant: str) -> str:
    transform, width, height = grid()
    path = LST_DIR.parent / f"composition_{variant}.tif"
    with rasterio.open(path, "w", driver="GTiff", width=width, height=height, count=1, dtype="uint8",
                       crs=f"EPSG:{UTM}", transform=transform, nodata=OUTSIDE, compress="deflate") as dst:
        dst.write(arr, 1)
    return str(path)


def inside_mask() -> np.ndarray:
    transform, width, height = grid()
    outline = gpd.read_file(BOUNDARY).to_crs(UTM)
    return ~geometry_mask(list(outline.geometry), (height, width), transform)


def summarise(lst_name: str = "lst_hot_all") -> pd.DataFrame:
    with rasterio.open(LST_DIR / f"{lst_name}.tif") as src:
        lst = src.read(1)
    inside = inside_mask()
    rows, grad = [], []
    for variant in VARIANTS:
        counts = group_counts(variant)
        cls = classify(counts)
        write_class(cls, variant)
        ok = inside & (cls != OUTSIDE) & np.isfinite(lst)
        n_all = int(ok.sum())
        for name in (*CLASS_ORDER, "unassigned"):
            code = UNASSIGNED if name == "unassigned" else CLASS_CODE[name]
            sel = ok & (cls == code)
            v = lst[sel]
            rows.append({
                "variant": variant,
                "class": name,
                "pixels": int(sel.sum()),
                "share": round(sel.sum() / n_all, 4) if n_all else np.nan,
                "km2": round(sel.sum() * PIXEL * PIXEL / 1e6, 2),
                "lst_mean": round(float(v.mean()), 2) if v.size else np.nan,
                "lst_median": round(float(np.median(v)), 2) if v.size else np.nan,
                "lst_p10": round(float(np.percentile(v, 10)), 2) if v.size else np.nan,
                "lst_p90": round(float(np.percentile(v, 90)), 2) if v.size else np.nan,
            })
        strict = classify(counts, strict=True)
        rows.append({"variant": variant, "class": "unassigned_strict_reading",
                     "share": round(float((ok & (strict == UNASSIGNED)).sum() / n_all), 4)})
        for k, grp in enumerate(GROUP_NAMES):
            rows.append({"variant": variant, "class": f"share_{grp}",
                         "share": round(float(counts[k][ok].sum() / (9 * n_all)), 4)})
            for n_cells in range(10):
                sel = ok & (counts[k] == n_cells)
                v = lst[sel]
                grad.append({"variant": variant, "group": grp, "cells_of_9": n_cells,
                             "pixels": int(sel.sum()),
                             "lst_mean": round(float(v.mean()), 2) if v.size else np.nan,
                             "lst_median": round(float(np.median(v)), 2) if v.size else np.nan})
    df = pd.DataFrame(rows)
    df.insert(0, "lst", lst_name)
    df.to_csv(COMPOSITION_CSV, index=False)
    g = pd.DataFrame(grad)
    g.insert(0, "lst", lst_name)
    g.to_csv(GRADIENT_CSV, index=False)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", default="lst_hot_all")
    ap.add_argument("--refetch", action="store_true")
    args = ap.parse_args()
    if args.refetch or not WORLDCOVER.exists():
        t0 = timing.start("WorldCover 10 m")
        timing.done("WorldCover 10 m", t0, fetch_worldcover())
    t0 = timing.start("composition classes", f"table S2 on {args.lst}")
    df = summarise(args.lst)
    timing.done("composition classes", t0, f"{len(df)} rows → {COMPOSITION_CSV.name}")
    with pd.option_context("display.width", 160):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
