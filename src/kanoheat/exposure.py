"""Who lives on the hottest ground: surface temperature, people by age and walking time per hex.

Hexes are the 200 m cells of 15-min-cities-nigeria, so each one already carries
its walking time to five clinics and five schools (PT_k).
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from scipy.spatial import cKDTree

from . import timing
from .lst import LST_DIR
from .paths import AGESEX_DIR, DATA_PROCESSED, HEXES, POP_TOTAL, SETTLEMENTS, UTM, WARDS

HEX_CSV = DATA_PROCESSED / "hex_heat.csv"
HEX_GPKG = DATA_PROCESSED / "kano_hex_heat.gpkg"
SUMMARY_CSV = DATA_PROCESSED / "exposure_summary.csv"
WARD_CSV = DATA_PROCESSED / "ward_heat.csv"

AGE_LAYERS = {
    "under5": "NGA_population_v3_0_agesex_under5.tif",
    "over65": "NGA_population_v3_0_agesex_over65.tif",
    "women15_49": "NGA_population_v3_0_agesex_f15_49.tif",
}
NAME_MAX_M = 3_000
NEAR_M = 400
WALK_LIMIT = 15.0


def zonal_mean(hexes_utm: gpd.GeoDataFrame, raster_path) -> np.ndarray:
    with rasterio.open(raster_path) as src:
        a = src.read(1)
        ids = rasterize(((g, i + 1) for i, g in enumerate(hexes_utm.geometry)), out_shape=a.shape,
                        transform=src.transform, fill=0, dtype="int32")
    ok = (ids > 0) & np.isfinite(a)
    n = len(hexes_utm) + 1
    s = np.bincount(ids[ok], weights=a[ok], minlength=n)
    c = np.bincount(ids[ok], minlength=n)
    with np.errstate(invalid="ignore"):
        return (s / c)[1:]


def zonal_sum(hexes_4326: gpd.GeoDataFrame, raster_path) -> np.ndarray:
    with rasterio.open(raster_path) as src:
        w, s, e, n = hexes_4326.total_bounds
        win = from_bounds(w - 0.01, s - 0.01, e + 0.01, n + 0.01, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win).astype("float64")
        tr = src.window_transform(win)
        nodata = src.nodata
    a[(a < 0) | ~np.isfinite(a)] = 0
    if nodata is not None:
        a[a == nodata] = 0
    ids = rasterize(((g, i + 1) for i, g in enumerate(hexes_4326.to_crs(4326).geometry)), out_shape=a.shape,
                    transform=tr, fill=0, dtype="int32", all_touched=False)
    return np.bincount(ids.ravel(), weights=a.ravel(), minlength=len(hexes_4326) + 1)[1:]


def attach_names(hexes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    wards = gpd.read_file(WARDS, layer="kano_wards").to_crs(UTM)[["wardname", "lganame", "geometry"]]
    cent = hexes.to_crs(UTM).copy()
    cent["geometry"] = cent.geometry.centroid
    joined = gpd.sjoin(cent, wards, how="left", predicate="within")
    joined = joined[~joined.index.duplicated()]
    miss = joined["wardname"].isna()
    if miss.any():
        near = gpd.sjoin_nearest(cent[miss.values], wards, how="left", max_distance=1_000)
        near = near[~near.index.duplicated()]
        joined.loc[near.index, ["wardname", "lganame"]] = near[["wardname", "lganame"]].values
    hexes["ward"] = joined["wardname"].values
    hexes["lga"] = joined["lganame"].values

    s = pd.read_csv(SETTLEMENTS)
    s = s[~s["kind"].isin(["junction", "roundabout"])]
    pts = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.lon, s.lat), crs=4326).to_crs(UTM)
    tree = cKDTree(np.c_[pts.geometry.x, pts.geometry.y])
    d, k = tree.query(np.c_[cent.geometry.x, cent.geometry.y])
    names = pts["name"].to_numpy()[k]
    hexes["place"] = np.where(d <= NAME_MAX_M, names, None)
    hexes["place_m"] = np.round(d, 0)
    hexes["place_label"] = [
        None if p is None else (p if dist < NEAR_M else f"Near {p}") for p, dist in zip(hexes["place"], d)
    ]
    return hexes


def build(lst_name: str = "lst_hot_all") -> gpd.GeoDataFrame:
    hexes = gpd.read_file(HEXES)
    keep = ["hex_id", "pop", "PT_k", "t_health", "t_school", "within_15", "off_network", "geometry"]
    hexes = hexes[[c for c in keep if c in hexes.columns]].copy()
    utm = hexes.to_crs(UTM)
    hexes["lst"] = zonal_mean(utm, LST_DIR / f"{lst_name}.tif")
    for year_path in sorted(LST_DIR.glob("lst_hot_20*.tif")):
        hexes[f"lst_{year_path.stem.split('_')[-1]}"] = zonal_mean(utm, year_path)
    hexes["pop_check"] = zonal_sum(hexes, POP_TOTAL)
    for col, fname in AGE_LAYERS.items():
        hexes[col] = zonal_sum(hexes, AGESEX_DIR / fname)
    hexes = attach_names(hexes)
    return hexes


def _wmean(v, w):
    ok = np.isfinite(v) & (w > 0)
    return float(np.sum(v[ok] * w[ok]) / np.sum(w[ok])) if ok.any() else np.nan


def summarise(h: gpd.GeoDataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    h = h[np.isfinite(h["lst"])].copy()
    pop = h["pop"].to_numpy()
    lst = h["lst"].to_numpy()
    rows = []

    def add(metric, value, note=""):
        rows.append({"metric": metric, "value": round(value, 4) if isinstance(value, float) else value, "note": note})

    add("hexes", len(h))
    add("people", float(pop.sum()), "GRID3 v3.0 on hexes")
    add("pop_check_ratio", float(h["pop_check"].sum() / pop.sum()), "raster re-sum / hex pop")
    add("lst_mean_area", float(np.nanmean(lst)), "unweighted over hexes")
    add("lst_weighted_pop", _wmean(lst, pop), "°C, population-weighted")
    by_lga = h.groupby("lga")[["pop", "under5", "over65"]].sum()
    for col in ["under5", "over65"]:
        share = by_lga[col] / by_lga["pop"]
        add(f"{col}_share_lga_min", float(share.min()), "GRID3 age-sex applies one age structure across metro Kano")
        add(f"{col}_share_lga_max", float(share.max()), "so age groups are counts, not a differential exposure")

    populated = h[h["pop"] >= 50]
    q90 = float(np.quantile(populated["lst"], 0.9))
    q10 = float(np.quantile(populated["lst"], 0.1))
    add("hottest_decile_threshold", q90, "°C, hexes with ≥ 50 people")
    add("coolest_decile_threshold", q10, "°C, hexes with ≥ 50 people")
    hot = h[h["lst"] >= q90]
    cool = h[h["lst"] <= q10]
    for col in ["pop", "under5", "over65", "women15_49"]:
        add(f"hottest_decile_{col}", float(hot[col].sum()))
        add(f"coolest_decile_{col}", float(cool[col].sum()))
    add("hottest_decile_share_pop", float(hot["pop"].sum() / pop.sum()))
    add("coolest_decile_share_pop", float(cool["pop"].sum() / pop.sum()))

    q80 = float(np.quantile(populated["lst"], 0.8))
    far = h["PT_k"] > WALK_LIMIT
    hot_far = (h["lst"] >= q80) & far
    add("hottest_quintile_threshold", q80, "°C, hexes with ≥ 50 people")
    add("hot_and_far_people", float(h.loc[hot_far, "pop"].sum()), f"hottest fifth and PT_k > {WALK_LIMIT:.0f} min")
    add("hot_and_far_under5", float(h.loc[hot_far, "under5"].sum()))
    add("hot_and_far_share_of_far", float(h.loc[hot_far, "pop"].sum() / h.loc[far, "pop"].sum()),
        "of people outside 15 minutes, share on the hottest fifth")
    w = populated["pop"].to_numpy()
    x = populated["lst"].to_numpy()
    y = populated["PT_k"].to_numpy()
    xm, ym = _wmean(x, w), _wmean(y, w)
    cov = np.sum(w * (x - xm) * (y - ym)) / w.sum()
    r = cov / np.sqrt((np.sum(w * (x - xm) ** 2) / w.sum()) * (np.sum(w * (y - ym) ** 2) / w.sum()))
    add("r_lst_walk_popweighted", float(r), "hexes with ≥ 50 people")

    g = h.groupby(["lga", "ward"], dropna=False)
    ward = pd.DataFrame({
        "people": g["pop"].sum(),
        "under5": g["under5"].sum(),
        "over65": g["over65"].sum(),
        "lst_popweighted": g.apply(lambda d: _wmean(d["lst"].to_numpy(), d["pop"].to_numpy()), include_groups=False),
        "lst_mean": g["lst"].mean(),
        "walk_popweighted": g.apply(lambda d: _wmean(d["PT_k"].to_numpy(), d["pop"].to_numpy()), include_groups=False),
        "people_hottest_decile": g.apply(lambda d: d.loc[d["lst"] >= q90, "pop"].sum(), include_groups=False),
        "top_place": g.apply(lambda d: d.sort_values("pop", ascending=False)["place"].dropna().head(1).squeeze()
                             if d["place"].notna().any() else None, include_groups=False),
    }).reset_index()
    ward = ward.sort_values("lst_popweighted", ascending=False).round(2)
    return pd.DataFrame(rows), ward


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", default="lst_hot_all")
    args = ap.parse_args()
    t0 = timing.start("exposure", f"hexes × {args.lst} × GRID3 age-sex")
    h = build(args.lst)
    h.to_file(HEX_GPKG, driver="GPKG")
    h.drop(columns="geometry").to_csv(HEX_CSV, index=False)
    summary, ward = summarise(h)
    summary.to_csv(SUMMARY_CSV, index=False)
    ward.to_csv(WARD_CSV, index=False)
    timing.done("exposure", t0, f"{len(h)} hexes → {HEX_CSV.name}, {SUMMARY_CSV.name}, {WARD_CSV.name}")
    with pd.option_context("display.width", 200, "display.max_colwidth", 60):
        print(summary.to_string(index=False))
        print(ward.head(12).to_string(index=False))
        print(ward.tail(8).to_string(index=False))


if __name__ == "__main__":
    main()
