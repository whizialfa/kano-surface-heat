"""NDVI, NDBI, MNDWI and bare-soil index from the same scenes as the LST medians.

Landsat C2 L2 surface reflectance: DN x 0.0000275 - 0.2. Indices are computed
per scene, then median per season-year, so they share dates with the LST.
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
BANDS = ("blue", "green", "red", "nir08", "swir16")
NAMES = ("NDVI", "NDBI", "MNDWI", "BSI")


def _nd(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def scene_indices(item, transform, width, height) -> np.ndarray:
    qa = _read(item.assets["qa_pixel"].href, transform, width, height, "uint16", QA_FILL)
    ok = ((qa & QA_FILL) == 0) & ((qa & QA_BAD) == 0)
    r = {}
    for band in BANDS:
        dn = _read(item.assets[band].href, transform, width, height, "uint16", 0)
        refl = dn.astype("float32") * SR_SCALE + SR_OFFSET
        refl[(dn == 0) | ~ok] = np.nan
        r[band] = refl
    ndvi = _nd(r["nir08"], r["red"])
    ndbi = _nd(r["swir16"], r["nir08"])
    mndwi = _nd(r["green"], r["swir16"])
    bsi = _nd(r["red"] + r["swir16"], r["nir08"] + r["blue"])
    return np.stack([ndvi, ndbi, mndwi, bsi]).astype("float32")


def season_indices(season: str, year: int, workers: int = 4) -> tuple[np.ndarray, int]:
    df = usable()
    ids = df[(df["season"] == season) & (df["year"] == year)].sort_values("date")["id"].tolist()
    if not ids:
        raise ValueError(f"no usable {season} scenes in {year}")
    transform, width, height = grid()
    items = items_by_id(ids)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        stack = list(pool.map(lambda it: scene_indices(it, transform, width, height), items))
    return np.nanmedian(np.stack(stack), axis=0).astype("float32"), len(ids)


def write(arr: np.ndarray, name: str) -> str:
    transform, width, height = grid()
    out = LST_DIR.parent / "indices" / f"{name}.tif"
    out.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out, "w", driver="GTiff", width=width, height=height, count=4, dtype="float32",
                       crs=f"EPSG:{UTM}", transform=transform, nodata=np.nan, compress="deflate",
                       tiled=True) as dst:
        dst.write(arr)
        for k, name_ in enumerate(NAMES, 1):
            dst.set_band_description(k, name_)
    return str(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="hot")
    ap.add_argument("--years", default="2015-2026")
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    a, b = (int(x) for x in args.years.split("-")) if "-" in args.years else (int(args.years),) * 2
    for yr in range(a, b + 1):
        if not args.redo and (LST_DIR.parent / "indices" / f"indices_{args.season}_{yr}.tif").exists():
            continue
        t0 = timing.start(f"indices {args.season} {yr}")
        try:
            arr, n = season_indices(args.season, yr)
        except ValueError as exc:
            timing.done(f"indices {args.season} {yr}", t0, str(exc))
            continue
        path = write(arr, f"indices_{args.season}_{yr}")
        timing.done(f"indices {args.season} {yr}", t0, f"{n} scenes → {path.split('/')[-1]}")


if __name__ == "__main__":
    main()
