"""Does building on farmland cool the ground by day? Change per hex, 2015–17 against 2024–26.

Built-up and cropland shares per hex come from our smoothed yearly land cover.
Heat is each hex's hot-season LST minus that year's rural-ring median, so a hot
or cool year does not pass for change.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import statsmodels.api as sm
from rasterio.features import rasterize

from . import timing
from .landcover import OUT_DIR
from .lst import grid
from .paths import DATA_PROCESSED, UTM

HEX_GPKG = DATA_PROCESSED / "kano_hex_heat.gpkg"
SERIES_CSV = DATA_PROCESSED / "lst_series.csv"
CHANGE_CSV = DATA_PROCESSED / "change_hex.csv"
SUMMARY_CSV = DATA_PROCESSED / "change_summary.csv"
EARLY = (2015, 2016, 2017)
LATE = (2024, 2025, 2026)
FARM_MAX = 0.25
BUILT_MIN = 0.5
STABLE_BUILT = 0.75


def hex_ids(hexes: gpd.GeoDataFrame) -> np.ndarray:
    transform, width, height = grid()
    return rasterize(((g, i + 1) for i, g in enumerate(hexes.to_crs(UTM).geometry)), out_shape=(height, width),
                     transform=transform, fill=0, dtype="int32")


def shares(ids: np.ndarray, n: int, year: int) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(OUT_DIR / f"lulc_smooth_{year}.tif") as src:
        c = src.read(1)
    ok = (ids > 0) & (c > 0)
    total = np.bincount(ids[ok], minlength=n + 1)[1:]
    built = np.bincount(ids[ok & (c == 1)], minlength=n + 1)[1:]
    crop = np.bincount(ids[ok & (c == 2)], minlength=n + 1)[1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        return built / total, crop / total


def build() -> pd.DataFrame:
    hexes = gpd.read_file(HEX_GPKG)
    ring = pd.read_csv(SERIES_CSV).set_index("year")["ring_median"]
    ids = hex_ids(hexes)
    n = len(hexes)
    out = hexes[["hex_id", "pop", "PT_k", "ward", "lga", "place"]].copy()
    for label, years in (("early", EARLY), ("late", LATE)):
        b, c, t = [], [], []
        for y in years:
            bs, cs = shares(ids, n, y)
            b.append(bs)
            c.append(cs)
            t.append(hexes[f"lst_{y}"].to_numpy() - ring.loc[y])
        out[f"built_{label}"] = np.nanmean(b, axis=0)
        out[f"crop_{label}"] = np.nanmean(c, axis=0)
        out[f"heat_{label}"] = np.nanmean(t, axis=0)
    out["d_built"] = out["built_late"] - out["built_early"]
    out["d_heat"] = out["heat_late"] - out["heat_early"]
    conditions = [
        (out["built_early"] < FARM_MAX) & (out["built_late"] >= BUILT_MIN),
        (out["built_early"] < FARM_MAX) & (out["built_late"] < FARM_MAX),
        (out["built_early"] >= STABLE_BUILT) & (out["built_late"] >= STABLE_BUILT),
    ]
    out["group"] = np.select(conditions, ["built over", "stayed open", "already built"], default="other")
    return out


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for g in ("built over", "stayed open", "already built", "other"):
        s = df[df["group"] == g]
        rows.append({
            "group": g, "hexes": len(s), "people_now": round(float(s["pop"].sum())),
            "built_early": round(float(s["built_early"].mean()), 3), "built_late": round(float(s["built_late"].mean()), 3),
            "heat_early": round(float(s["heat_early"].mean()), 2), "heat_late": round(float(s["heat_late"].mean()), 2),
            "d_heat_mean": round(float(s["d_heat"].mean()), 2), "d_heat_median": round(float(s["d_heat"].median()), 2),
            "d_heat_iqr": f"{s['d_heat'].quantile(.25):.2f} to {s['d_heat'].quantile(.75):.2f}",
        })
    bo = df[df["group"] == "built over"]["d_heat"]
    so = df[df["group"] == "stayed open"]["d_heat"]
    rows.append({"group": "built over minus stayed open", "d_heat_mean": round(float(bo.mean() - so.mean()), 2),
                 "d_heat_median": round(float(bo.median() - so.median()), 2)})
    ok = df.dropna(subset=["d_built", "d_heat"])
    res = sm.OLS(ok["d_heat"], sm.add_constant(ok["d_built"])).fit()
    rows.append({"group": "slope, all hexes", "d_heat_mean": round(float(res.params["d_built"]) / 10, 3),
                 "hexes": len(ok), "d_heat_iqr": f"°C per 10 points of built-up; R² {res.rsquared:.3f}"})
    return pd.DataFrame(rows)


IO_EARLY = (2017, 2018)
IO_LATE = (2022, 2023)
IO_CSV = DATA_PROCESSED / "change_summary_io.csv"


def independent_check() -> pd.DataFrame:
    """Same test with Impact Observatory (Sentinel-2, no thermal), so the land cover cannot share noise with the LST."""
    from .landcover import to30

    hexes = gpd.read_file(HEX_GPKG)
    ring = pd.read_csv(SERIES_CSV).set_index("year")["ring_median"]
    ids = hex_ids(hexes)
    n = len(hexes)
    out = hexes[["hex_id", "pop"]].copy()
    for label, years in (("early", IO_EARLY), ("late", IO_LATE)):
        b, t = [], []
        for y in years:
            major, _ = to30("io", y)
            ok = (ids > 0) & (major > 0)
            total = np.bincount(ids[ok], minlength=n + 1)[1:]
            built = np.bincount(ids[ok & (major == 1)], minlength=n + 1)[1:]
            with np.errstate(invalid="ignore", divide="ignore"):
                b.append(built / total)
            t.append(hexes[f"lst_{y}"].to_numpy() - ring.loc[y])
        out[f"built_{label}"] = np.nanmean(b, axis=0)
        out[f"heat_{label}"] = np.nanmean(t, axis=0)
    out["d_heat"] = out["heat_late"] - out["heat_early"]
    out["d_built"] = out["built_late"] - out["built_early"]
    conditions = [
        (out["built_early"] < FARM_MAX) & (out["built_late"] >= BUILT_MIN),
        (out["built_early"] < FARM_MAX) & (out["built_late"] < FARM_MAX),
        (out["built_early"] >= STABLE_BUILT) & (out["built_late"] >= STABLE_BUILT),
    ]
    out["group"] = np.select(conditions, ["built over", "stayed open", "already built"], default="other")
    s = summarise(out.assign(ward=None, lga=None, place=None, PT_k=np.nan, crop_early=np.nan, crop_late=np.nan))
    s.insert(0, "source", f"Impact Observatory {IO_EARLY[0]}–{IO_EARLY[-1]} vs {IO_LATE[0]}–{IO_LATE[-1]}")
    s.to_csv(IO_CSV, index=False)
    return s


CHANGE_GPKG = DATA_PROCESSED / "kano_hex_change.gpkg"
PLATE_CODE = {"built over": 1, "other": 2, "already built": 3, "stayed open": 4}


def write_plate_layer(df: pd.DataFrame) -> None:
    hexes = gpd.read_file(HEX_GPKG)[["hex_id", "geometry"]]
    g = hexes.merge(df[["hex_id", "group", "built_early", "built_late", "d_heat", "pop"]], on="hex_id")
    g["change_code"] = g["group"].map(PLATE_CODE).astype("int16")
    g.to_file(CHANGE_GPKG, layer="kano_hex_change", driver="GPKG")


def main() -> None:
    t0 = timing.start("land-cover change test", "hexes, 2015–17 against 2024–26")
    df = build()
    df.to_csv(CHANGE_CSV, index=False)
    write_plate_layer(df)
    s = summarise(df)
    s.to_csv(SUMMARY_CSV, index=False)
    io = independent_check()
    with pd.option_context("display.width", 220):
        print(io.to_string(index=False))
    timing.done("land-cover change test", t0, f"{len(df)} hexes → {SUMMARY_CSV.name}")
    with pd.option_context("display.width", 220):
        print(s.to_string(index=False))
        top = df[df["group"] == "built over"].groupby(["lga", "ward"]).agg(
            hexes=("hex_id", "size"), d_heat=("d_heat", "mean")).sort_values("hexes", ascending=False).head(8)
        print(top.round(2).to_string())


if __name__ == "__main__":
    main()
