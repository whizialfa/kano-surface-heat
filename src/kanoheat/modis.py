"""Day and night: does Kano stay cooler than its farmland after dark?

MODIS MOD11A2 (Terra, ~10:30 and ~22:30) and MYD11A2 (Aqua, ~13:30 and ~01:30)
8-day clear-sky composites, 1 km, from Planetary Computer. Same outline, rural
ring and old-city / fringe split as the Landsat analysis, on a 1 km UTM grid.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer as pc
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT

from . import timing
from .lst import RING_M
from .paths import BOUNDARY, DATA_PROCESSED, UTM
from .scenes import GDAL_ENV, SEASON, STAC
from .series import CORE_LGAS, FRINGE_LGAS

COLLECTION = "modis-11A2-061"
PIXEL = 1000.0
SCALE = 0.02
MIN_VALID = 0.8
CONTRASTS_CSV = DATA_PROCESSED / "modis_contrasts.csv"
SUMMARY_CSV = DATA_PROCESSED / "modis_summary.csv"
OVERPASS = {
    ("terra", "LST_Day_1km"): "Terra 10:30",
    ("aqua", "LST_Day_1km"): "Aqua 13:30",
    ("terra", "LST_Night_1km"): "Terra 22:30",
    ("aqua", "LST_Night_1km"): "Aqua 01:30",
}
OVERPASS_ORDER = ("Terra 10:30", "Aqua 13:30", "Terra 22:30", "Aqua 01:30")


def grid():
    outline = gpd.read_file(BOUNDARY).to_crs(UTM)
    xmin, ymin, xmax, ymax = outline.buffer(RING_M + 2_000).total_bounds
    xmin, ymin = np.floor(xmin / PIXEL) * PIXEL, np.floor(ymin / PIXEL) * PIXEL
    xmax, ymax = np.ceil(xmax / PIXEL) * PIXEL, np.ceil(ymax / PIXEL) * PIXEL
    w, h = int((xmax - xmin) / PIXEL), int((ymax - ymin) / PIXEL)
    return from_origin(xmin, ymax, PIXEL, PIXEL), w, h


def masks():
    transform, w, h = grid()
    outline = gpd.read_file(BOUNDARY).to_crs(UTM)

    def m(geoms):
        return ~geometry_mask(list(geoms), (h, w), transform)

    inside = m(outline.geometry)
    ring = m(outline.buffer(RING_M).geometry) & ~m(outline.buffer(1_000).geometry)
    lgas = gpd.read_file(DATA_PROCESSED / "kano_metro_lgas.gpkg").to_crs(UTM)
    col = next(c for c in lgas.columns if c.lower() in ("lganame", "lga_name", "name", "adm2_en", "shapename"))
    core = m(lgas[lgas[col].isin(CORE_LGAS)].geometry)
    fringe = m(lgas[lgas[col].isin(FRINGE_LGAS)].geometry)
    return inside, ring, core, fringe


def search(years: range, months=(3, 4, 5)):
    outline = gpd.read_file(BOUNDARY).to_crs(4326)
    cat = Client.open(STAC, modifier=pc.sign_inplace)
    items = []
    for yr in years:
        found = cat.search(collections=[COLLECTION], bbox=list(outline.total_bounds),
                           datetime=f"{yr}-{months[0]:02d}-01/{yr}-{months[-1]:02d}-31").items()
        items.extend(found)
    return items


def _read(href, transform, w, h):
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(pc.sign(href)) as src:
            with WarpedVRT(src, crs=f"EPSG:{UTM}", transform=transform, width=w, height=h,
                           resampling=Resampling.nearest, src_nodata=0, nodata=0) as vrt:
                dn = vrt.read(1, out_dtype="uint16")
    out = np.full(dn.shape, np.nan, dtype="float32")
    ok = dn > 0
    out[ok] = dn[ok].astype("float32") * SCALE - 273.15
    return out


def contrasts(item, transform, w, h, masks_):
    inside, ring, core, fringe = masks_
    platform = "terra" if item.id.startswith("MOD") else "aqua"
    date = item.properties.get("start_datetime", item.properties.get("datetime"))[:10]
    rows = []
    for band in ("LST_Day_1km", "LST_Night_1km"):
        a = _read(item.assets[band].href, transform, w, h)
        vi = np.isfinite(a[inside]).mean()
        vr = np.isfinite(a[ring]).mean()
        row = {"id": item.id, "date": date, "platform": platform, "overpass": OVERPASS[(platform, band)],
               "valid_city": round(float(vi), 3), "valid_ring": round(float(vr), 3)}
        if vi >= MIN_VALID and vr >= MIN_VALID:
            city, rng = np.nanmedian(a[inside]), np.nanmedian(a[ring])
            row.update({
                "city_median": round(float(city), 2), "ring_median": round(float(rng), 2),
                "city_minus_ring": round(float(city - rng), 2),
                "fringe_minus_core": round(float(np.nanmean(a[fringe]) - np.nanmean(a[core])), 2),
            })
        rows.append(row)
    return rows


def run(years: range, months=(3, 4, 5), workers: int = 8) -> pd.DataFrame:
    transform, w, h = grid()
    m = masks()
    items = search(years, months)
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(lambda it: contrasts(it, transform, w, h, m), items):
            rows.extend(part)
    df = pd.DataFrame(rows).sort_values(["date", "overpass"]).reset_index(drop=True)
    df["month"] = pd.to_datetime(df["date"]).dt.month
    df["season"] = df["month"].map(SEASON)
    return df


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    ok = df.dropna(subset=["city_minus_ring"])
    rows = []
    for season, g in ok.groupby("season"):
        for op in OVERPASS_ORDER:
            s = g[g["overpass"] == op]
            if s.empty:
                continue
            rows.append({
                "season": season, "overpass": op, "composites": len(s),
                "city_minus_ring_median": round(float(s["city_minus_ring"].median()), 2),
                "city_cooler_share": round(float((s["city_minus_ring"] < 0).mean()), 3),
                "fringe_minus_core_median": round(float(s["fringe_minus_core"].median()), 2),
                "fringe_hotter_share": round(float((s["fringe_minus_core"] > 0).mean()), 3),
                "city_median": round(float(s["city_median"].median()), 1),
                "ring_median": round(float(s["ring_median"].median()), 1),
            })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2015-2026")
    ap.add_argument("--all-seasons", action="store_true")
    args = ap.parse_args()
    a, b = (int(x) for x in args.years.split("-"))
    months = tuple(range(1, 13)) if args.all_seasons else (3, 4, 5)
    t0 = timing.start("MODIS day and night", f"{COLLECTION}, {a}-{b}, months {months[0]}-{months[-1]}")
    df = run(range(a, b + 1), months)
    df.to_csv(CONTRASTS_CSV, index=False)
    summary = summarise(df)
    summary.to_csv(SUMMARY_CSV, index=False)
    timing.done("MODIS day and night", t0, f"{df['id'].nunique()} composites → {SUMMARY_CSV.name}")
    with pd.option_context("display.width", 200):
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
