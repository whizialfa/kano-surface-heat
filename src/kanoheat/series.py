"""Year-by-year hot-season statistics and the pooled multi-year surface.

The pooled surface is the per-pixel median of the yearly medians, so a year with
six clear scenes does not outvote a year with one.
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from . import timing
from .lst import LST_DIR, RING_M, grid, write
from .paths import BOUNDARY, DATA_PROCESSED, UTM

SERIES_CSV = DATA_PROCESSED / "lst_series.csv"
LGA_CSV = DATA_PROCESSED / "lst_by_lga.csv"
SCENE_CSV = DATA_PROCESSED / "lst_by_scene.csv"
CORE_LGAS = ("Kano Municipal", "Dala", "Gwale", "Fagge", "Nassarawa", "Tarauni")
FRINGE_LGAS = ("Ungogo", "Kumbotso")


def masks():
    transform, width, height = grid()
    outline = gpd.read_file(BOUNDARY).to_crs(UTM)

    def m(geoms):
        return ~geometry_mask(list(geoms), (height, width), transform)

    inside = m(outline.geometry)
    ring = m(outline.buffer(RING_M).geometry) & ~m(outline.buffer(1_000).geometry)
    lgas = gpd.read_file(DATA_PROCESSED / "kano_metro_lgas.gpkg").to_crs(UTM)
    col = next(c for c in lgas.columns if c.lower() in ("lganame", "lga_name", "name", "adm2_en", "shapename"))
    by_lga = {r[col]: m([r.geometry]) for _, r in lgas.iterrows()}
    return inside, ring, by_lga


def _stats(a, sel):
    v = a[sel & np.isfinite(a)]
    return v.mean(), np.median(v), v.std()


def yearly(season: str = "hot") -> tuple[pd.DataFrame, pd.DataFrame]:
    inside, ring, by_lga = masks()
    rows, lrows = [], []
    for path in sorted(LST_DIR.glob(f"lst_{season}_20*.tif")):
        year = int(path.stem.split("_")[-1])
        with rasterio.open(path) as src:
            a = src.read(1)
        i_mean, i_med, i_sd = _stats(a, inside)
        r_mean, r_med, _ = _stats(a, ring)
        core = np.zeros_like(inside)
        fringe = np.zeros_like(inside)
        for name, msk in by_lga.items():
            mean, med, _ = _stats(a, msk)
            lrows.append({"season": season, "year": year, "lga": name, "lst_mean": round(mean, 2),
                          "lst_median": round(med, 2)})
            if name in CORE_LGAS:
                core |= msk
            elif name in FRINGE_LGAS:
                fringe |= msk
        c_mean = _stats(a, core)[0]
        f_mean = _stats(a, fringe)[0]
        rows.append({
            "season": season, "year": year,
            "outline_mean": round(i_mean, 2), "outline_median": round(i_med, 2), "outline_sd": round(i_sd, 2),
            "ring_mean": round(r_mean, 2), "ring_median": round(r_med, 2),
            "suhi_median": round(i_med - r_med, 2),
            "core_mean": round(c_mean, 2), "fringe_mean": round(f_mean, 2),
            "fringe_minus_core": round(f_mean - c_mean, 2),
            "hot_spot_c": round(i_mean + 2 * i_sd, 2), "cold_spot_c": round(i_mean - 2 * i_sd, 2),
            "valid_inside": round(float(np.isfinite(a[inside]).mean()), 4),
        })
    return pd.DataFrame(rows), pd.DataFrame(lrows)


def per_scene(season: str = "hot", workers: int = 6) -> pd.DataFrame:
    """City minus ring and fringe minus core for every usable scene, not just yearly medians."""
    from concurrent.futures import ThreadPoolExecutor

    from .lst import items_by_id, scene_lst
    from .scenes import usable

    inside, ring, by_lga = masks()
    core = np.zeros_like(inside)
    fringe = np.zeros_like(inside)
    for name, msk in by_lga.items():
        if name in FRINGE_LGAS:
            fringe |= msk
        elif name in CORE_LGAS:
            core |= msk
    transform, width, height = grid()
    df = usable()
    pick = df[df["season"] == season].sort_values("date")
    items = items_by_id(pick["id"].tolist())

    def one(it):
        a = scene_lst(it, transform, width, height)
        city, rng = np.nanmedian(a[inside]), np.nanmedian(a[ring])
        return {
            "id": it.id, "date": it.properties["datetime"][:10],
            "city_median": round(float(city), 2), "ring_median": round(float(rng), 2),
            "city_minus_ring": round(float(city - rng), 2),
            "fringe_minus_core": round(float(np.nanmean(a[fringe]) - np.nanmean(a[core])), 2),
        }

    with ThreadPoolExecutor(max_workers=workers) as pool_:
        rows = list(pool_.map(one, items))
    out = pd.DataFrame(rows).sort_values("date")
    out.to_csv(SCENE_CSV, index=False)
    return out


UTFVI_ZHANG = ((-np.inf, 0.0, "none"), (0.0, 0.005, "weak"), (0.005, 0.010, "middle"),
               (0.010, 0.015, "strong"), (0.015, 0.020, "stronger"), (0.020, np.inf, "strongest"))
UTFVI_ANCHOR = ((-np.inf, -0.149, "weak"), (-0.149, -0.0543, "normal"), (-0.0543, 0.0403, "middle"),
                (0.0403, 0.1349, "strong"), (0.1349, 0.2295, "stronger"), (0.2295, np.inf, "strongest"))
THERMAL_CSV = DATA_PROCESSED / "thermal_classes.csv"


def thermal_classes(lst_name: str = "lst_hot_all") -> pd.DataFrame:
    """Hot and cold spots (μ ± 2σ) and UTFVI shares inside the outline."""
    inside, _, _ = masks()
    with rasterio.open(LST_DIR / f"{lst_name}.tif") as src:
        a = src.read(1)
    v = a[inside & np.isfinite(a)]
    mu, sd = float(v.mean()), float(v.std())
    km2 = lambda n: round(n * 900 / 1e6, 2)
    rows = [
        {"measure": "mean_c", "value": round(mu, 2)},
        {"measure": "sd_c", "value": round(sd, 2)},
        {"measure": "hot_spot_threshold_c", "value": round(mu + 2 * sd, 2)},
        {"measure": "cold_spot_threshold_c", "value": round(mu - 2 * sd, 2)},
        {"measure": "hot_spot_km2", "value": km2((v > mu + 2 * sd).sum())},
        {"measure": "cold_spot_km2", "value": km2((v < mu - 2 * sd).sum())},
    ]
    k = v + 273.15
    utfvi_k = (k - k.mean()) / k.mean()
    utfvi_c = (v - mu) / mu
    for label, idx, table in (("zhang_kelvin", utfvi_k, UTFVI_ZHANG), ("anchor_celsius", utfvi_c, UTFVI_ANCHOR)):
        for lo, hi, cls in table:
            sel = (idx > lo) & (idx <= hi)
            rows.append({"measure": f"utfvi_{label}_{cls}_share", "value": round(float(sel.mean()), 4)})
    df = pd.DataFrame(rows)
    df.insert(0, "lst", lst_name)
    df.to_csv(THERMAL_CSV, index=False)
    return df


def pool(season: str = "hot", name: str | None = None) -> str:
    paths = sorted(LST_DIR.glob(f"lst_{season}_20*.tif"))
    stack = []
    for p in paths:
        with rasterio.open(p) as src:
            stack.append(src.read(1))
    arr = np.nanmedian(np.stack(stack), axis=0).astype("float32")
    return write(arr, name or f"lst_{season}_all")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="hot")
    ap.add_argument("--scenes", action="store_true", help="per-scene contrasts (network)")
    args = ap.parse_args()
    if args.scenes:
        t0 = timing.start("LST per scene", args.season)
        sc = per_scene(args.season)
        neg = int((sc["city_minus_ring"] < 0).sum())
        pos = int((sc["fringe_minus_core"] > 0).sum())
        timing.done("LST per scene", t0, f"{len(sc)} scenes; city cooler than ring in {neg}; fringe hotter in {pos}")
        with pd.option_context("display.width", 200):
            print(sc.to_string(index=False))
        return
    t0 = timing.start("LST series", args.season)
    df, lg = yearly(args.season)
    df.to_csv(SERIES_CSV, index=False)
    lg.to_csv(LGA_CSV, index=False)
    pooled = pool(args.season)
    thermal_classes(f"lst_{args.season}_all")
    timing.done("LST series", t0, f"{len(df)} years → {SERIES_CSV.name}; pooled {pooled.split('/')[-1]}; "
                                  f"{THERMAL_CSV.name}")
    with pd.option_context("display.width", 200):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
