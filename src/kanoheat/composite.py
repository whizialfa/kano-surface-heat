"""Per-season, per-year surface reflectance composites for land-cover classification.

Six Landsat C2 L2 bands, per-pixel median of the season's usable scenes (the same
scenes as the LST for the hot season), on the fixed 30 m grid. Stored as
reflectance x 10000 in int16.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import rasterio

from . import timing
from .lst import LST_DIR, _read, grid, items_by_id
from .paths import UTM
from .scenes import QA_BAD, QA_FILL, usable

SR_SCALE = 0.0000275
SR_OFFSET = -0.2
BANDS = ("blue", "green", "red", "nir08", "swir16", "swir22")
COMPOSITE_DIR = LST_DIR.parent / "composites"
NODATA = -32768


def scene_bands(item, transform, width, height) -> np.ndarray:
    qa = _read(item.assets["qa_pixel"].href, transform, width, height, "uint16", QA_FILL)
    ok = ((qa & QA_FILL) == 0) & ((qa & QA_BAD) == 0)
    out = np.full((len(BANDS), height, width), np.nan, dtype="float32")
    for k, band in enumerate(BANDS):
        dn = _read(item.assets[band].href, transform, width, height, "uint16", 0)
        refl = dn.astype("float32") * SR_SCALE + SR_OFFSET
        good = ok & (dn > 0)
        out[k][good] = refl[good]
    return out


def season_composite(season: str, year: int, workers: int = 4) -> tuple[np.ndarray, int]:
    df = usable()
    ids = df[(df["season"] == season) & (df["year"] == year)].sort_values("date")["id"].tolist()
    if not ids:
        raise ValueError(f"no usable {season} scenes in {year}")
    transform, width, height = grid()
    items = items_by_id(ids)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        stack = list(pool.map(lambda it: scene_bands(it, transform, width, height), items))
    with np.errstate(all="ignore"):
        med = np.nanmedian(np.stack(stack), axis=0)
    out = np.where(np.isfinite(med), np.round(med * 10000), NODATA).astype("int16")
    return out, len(ids)


def path(season: str, year: int):
    return COMPOSITE_DIR / f"{season}_{year}.tif"


def write(arr: np.ndarray, season: str, year: int) -> str:
    transform, width, height = grid()
    out = path(season, year)
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", driver="GTiff", width=width, height=height, count=len(BANDS), dtype="int16",
                       crs=f"EPSG:{UTM}", transform=transform, nodata=NODATA, compress="deflate",
                       predictor=2, tiled=True) as dst:
        dst.write(arr)
        for k, b in enumerate(BANDS, 1):
            dst.set_band_description(k, b)
    return str(out)


def read(season: str, year: int) -> np.ndarray:
    """(6, H, W) float32 reflectance with NaN for no data."""
    with rasterio.open(path(season, year)) as src:
        a = src.read().astype("float32")
    a[a == NODATA] = np.nan
    return a / 10000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="hot,wet")
    ap.add_argument("--years", default="2015-2026")
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    a, b = (int(x) for x in args.years.split("-")) if "-" in args.years else (int(args.years),) * 2
    for yr in range(a, b + 1):
        for season in args.seasons.split(","):
            if path(season, yr).exists() and not args.redo:
                continue
            t0 = timing.start(f"composite {season} {yr}")
            try:
                arr, n = season_composite(season, yr)
            except ValueError as exc:
                timing.done(f"composite {season} {yr}", t0, str(exc))
                continue
            out = write(arr, season, yr)
            timing.done(f"composite {season} {yr}", t0, f"{n} scenes → {out.split('/')[-1]}")


if __name__ == "__main__":
    main()
