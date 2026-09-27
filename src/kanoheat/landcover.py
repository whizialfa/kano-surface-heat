"""Our own land cover for every year, from the same Landsat scenes as the heat.

Features: hot-season and wet-season reflectance composites (six bands each) plus
NDVI, NDBI, MNDWI and the bare-soil index in the hot season and NDVI and MNDWI in
the wet season. Dry-season farmland is bare in March and green in August, which
is what separates it from roofs and open ground.

Labels: 30 m cells whose nine 10 m WorldCover cells all agree, in both 2020 and
2021. A random forest trained on 2020 and 2021 is applied to 2015–2026 and
checked against Impact Observatory's independent annual maps (2017–2023).
"""

from __future__ import annotations

import argparse

import joblib
import numpy as np
import pandas as pd
import planetary_computer as pc
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, f1_score
from sklearn.model_selection import GroupKFold

from . import timing
from .composite import read as read_composite
from .composition import inside_mask
from .lst import LST_DIR, PIXEL, grid
from .paths import BOUNDARY, DATA_PROCESSED, UTM
from .scenes import GDAL_ENV, STAC
from .series import masks as lga_masks

import geopandas as gpd

REF_DIR = LST_DIR.parent / "ref"
OUT_DIR = LST_DIR.parent / "lulc"
MODEL = LST_DIR.parent / "lulc_rf.joblib"
ACCURACY_CSV = DATA_PROCESSED / "lulc_accuracy.csv"
CONFUSION_CSV = DATA_PROCESSED / "lulc_confusion.csv"
SHARES_CSV = DATA_PROCESSED / "lulc_shares_by_year.csv"

CLASSES = {1: "Built-up", 2: "Cropland", 3: "Bare ground", 4: "Grass and shrub", 5: "Trees", 6: "Water"}
WORLDCOVER_LUT = {50: 1, 40: 2, 60: 3, 30: 4, 20: 4, 10: 5, 80: 6, 90: 6, 95: 6, 100: 4}
IO_LUT = {7: 1, 5: 2, 8: 3, 11: 4, 2: 5, 1: 6, 4: 6}
REFS = {
    "worldcover": ("esa-worldcover", "map", lambda it, y: f"_{y}_" in it.id),
    "io": ("io-lulc-annual-v02", "data", lambda it, y: it.id.endswith(f"-{y}")),
}
FEATURES = (
    [f"hot_{b}" for b in ("blue", "green", "red", "nir", "swir1", "swir2")]
    + ["hot_ndvi", "hot_ndbi", "hot_mndwi", "hot_bsi"]
    + [f"wet_{b}" for b in ("blue", "green", "red", "nir", "swir1", "swir2")]
    + ["wet_ndvi", "wet_mndwi"]
)
PER_CLASS = 3000
TRAIN_YEARS = (2020, 2021)
BLOCK_PX = 100  # 3 km spatial blocks for cross-validation


def _grid10():
    t30, w30, h30 = grid()
    return Affine(PIXEL / 3, 0, t30.c, 0, -PIXEL / 3, t30.f), w30 * 3, h30 * 3


def ref_path(kind: str, year: int):
    return REF_DIR / f"{kind}_{year}_10m.tif"


def fetch_ref(kind: str, year: int) -> str:
    coll, asset, pick = REFS[kind]
    t10, w10, h10 = _grid10()
    outline = gpd.read_file(BOUNDARY).to_crs(4326)
    cat = Client.open(STAC, modifier=pc.sign_inplace)
    items = [it for it in cat.search(collections=[coll], bbox=list(outline.buffer(0.2).total_bounds)).items()
             if pick(it, year)]
    if not items:
        raise ValueError(f"no {kind} tiles for {year}")
    out = np.zeros((h10, w10), dtype="uint8")
    for it in items:
        with rasterio.Env(**GDAL_ENV):
            with rasterio.open(pc.sign(it.assets[asset].href)) as src:
                with WarpedVRT(src, crs=f"EPSG:{UTM}", transform=t10, width=w10, height=h10,
                               resampling=Resampling.nearest, src_nodata=0, nodata=0) as vrt:
                    part = vrt.read(1)
        out = np.where(out == 0, part, out)
    p = ref_path(kind, year)
    p.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(p, "w", driver="GTiff", width=w10, height=h10, count=1, dtype="uint8",
                       crs=f"EPSG:{UTM}", transform=t10, nodata=0, compress="deflate", tiled=True) as dst:
        dst.write(out, 1)
    return f"{kind} {year}: {len(items)} tiles"


def to30(kind: str, year: int) -> tuple[np.ndarray, np.ndarray]:
    """Majority class and purity (cells of nine) at 30 m, in our six classes."""
    with rasterio.open(ref_path(kind, year)) as src:
        a = src.read(1)
    lut = np.zeros(256, dtype="uint8")
    for code, cls in (WORLDCOVER_LUT if kind == "worldcover" else IO_LUT).items():
        lut[code] = cls
    c = lut[a]
    _, w30, h30 = grid()
    blocks = c[: h30 * 3, : w30 * 3].reshape(h30, 3, w30, 3).transpose(0, 2, 1, 3).reshape(h30, w30, 9)
    counts = np.stack([(blocks == k).sum(axis=2) for k in range(1, 7)], axis=-1)
    major = (counts.argmax(axis=-1) + 1).astype("uint8")
    purity = counts.max(axis=-1).astype("uint8")
    major[counts.sum(axis=-1) == 0] = 0
    return major, purity


def _nd(a, b):
    with np.errstate(divide="ignore", invalid="ignore"):
        return (a - b) / (a + b)


def features(year: int) -> np.ndarray:
    hot = read_composite("hot", year)
    wet = read_composite("wet", year)
    blue, green, red, nir, sw1, _ = hot
    hot_idx = [_nd(nir, red), _nd(sw1, nir), _nd(green, sw1), _nd(red + sw1, nir + blue)]
    wet_idx = [_nd(wet[3], wet[2]), _nd(wet[1], wet[4])]
    return np.concatenate([hot, np.stack(hot_idx), wet, np.stack(wet_idx)]).astype("float32")


def training_samples(seed: int = 42) -> pd.DataFrame:
    wc20, p20 = to30("worldcover", 2020)
    wc21, p21 = to30("worldcover", 2021)
    stable = (wc20 == wc21) & (p20 == 9) & (p21 == 9) & (wc21 > 0)
    rng = np.random.default_rng(seed)
    rows = []
    for year in TRAIN_YEARS:
        f = features(year)
        ok = stable & np.all(np.isfinite(f), axis=0)
        for cls in CLASSES:
            r, c = np.nonzero(ok & (wc21 == cls))
            if len(r) == 0:
                continue
            k = rng.choice(len(r), size=min(PER_CLASS, len(r)), replace=False)
            d = pd.DataFrame(f[:, r[k], c[k]].T, columns=FEATURES)
            d["label"] = cls
            d["year"] = year
            d["block"] = (r[k] // BLOCK_PX) * 10_000 + (c[k] // BLOCK_PX)
            rows.append(d)
    return pd.concat(rows, ignore_index=True)


def _model():
    return RandomForestClassifier(n_estimators=250, min_samples_leaf=2, max_features="sqrt", n_jobs=-1,
                                  random_state=42)


def train() -> pd.DataFrame:
    df = training_samples()
    X, y, groups = df[FEATURES].to_numpy(), df["label"].to_numpy(), df["block"].to_numpy()
    pred = np.zeros_like(y)
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        m = _model().fit(X[tr], y[tr])
        pred[te] = m.predict(X[te])
    labels = sorted(CLASSES)
    acc = [{"metric": "overall_accuracy", "value": round(accuracy_score(y, pred), 4)},
           {"metric": "kappa", "value": round(cohen_kappa_score(y, pred), 4)},
           {"metric": "samples", "value": len(y)}]
    for cls, f1 in zip(labels, f1_score(y, pred, labels=labels, average=None)):
        acc.append({"metric": f"f1_{CLASSES[cls]}", "value": round(float(f1), 4)})
        acc.append({"metric": f"n_{CLASSES[cls]}", "value": int((y == cls).sum())})
    pd.DataFrame(confusion_matrix(y, pred, labels=labels), index=[CLASSES[c] for c in labels],
                 columns=[CLASSES[c] for c in labels]).to_csv(CONFUSION_CSV)
    final = _model().fit(X, y)
    imp = sorted(zip(FEATURES, final.feature_importances_), key=lambda t: -t[1])[:6]
    for name, v in imp:
        acc.append({"metric": f"importance_{name}", "value": round(float(v), 4)})
    joblib.dump(final, MODEL)
    out = pd.DataFrame(acc)
    out.to_csv(ACCURACY_CSV, index=False)
    return out


def _write_class(arr: np.ndarray, name: str) -> str:
    transform, width, height = grid()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / f"{name}.tif"
    with rasterio.open(p, "w", driver="GTiff", width=width, height=height, count=1, dtype="uint8",
                       crs=f"EPSG:{UTM}", transform=transform, nodata=0, compress="deflate") as dst:
        dst.write(arr, 1)
    return str(p)


def proba_path(year: int):
    return OUT_DIR / f"proba_{year}.npy"


def predict(year: int, model=None) -> str:
    """Hard classes plus class probabilities (float16, NaN where the year has no clear view)."""
    model = model or joblib.load(MODEL)
    f = features(year)
    ok = np.all(np.isfinite(f), axis=0)
    X = f[:, ok].T
    prob = np.full((len(CLASSES),) + ok.shape, np.nan, dtype="float16")
    p_ok = np.empty((len(X), len(CLASSES)), dtype="float32")
    for k in range(0, len(X), 500_000):
        p_ok[k:k + 500_000] = model.predict_proba(X[k:k + 500_000])
    prob[:, ok] = p_ok.T.astype("float16")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(proba_path(year), prob)
    out = np.zeros(ok.shape, dtype="uint8")
    out[ok] = (p_ok.argmax(axis=1) + 1).astype("uint8")
    return _write_class(out, f"lulc_{year}")


def smooth(years, window: int = 1) -> list[str]:
    """Three-year mean of class probabilities: fills cloud gaps and damps one-year flips."""
    years = list(years)
    written = []
    for y in years:
        stack = [np.load(proba_path(n)).astype("float32") for n in range(y - window, y + window + 1)
                 if n in years and proba_path(n).exists()]
        with np.errstate(all="ignore"):
            mean = np.nanmean(np.stack(stack), axis=0)
        valid = np.all(np.isfinite(mean), axis=0)
        out = np.zeros(valid.shape, dtype="uint8")
        out[valid] = (np.nanargmax(mean[:, valid], axis=0) + 1).astype("uint8")
        written.append(_write_class(out, f"lulc_smooth_{y}"))
    return written


def shares(years) -> pd.DataFrame:
    inside, _, by_lga = lga_masks()
    fringe = np.zeros_like(inside)
    for name in ("Ungogo", "Kumbotso"):
        fringe |= by_lga[name]
    core = inside & ~fringe
    rows = []

    def add(source, year, arr):
        for zone, m in (("metro", inside), ("old_city", core), ("fringe", fringe)):
            valid = m & (arr > 0)
            n = valid.sum()
            for cls, name in CLASSES.items():
                rows.append({"source": source, "year": year, "zone": zone, "class": name,
                             "share": round(float((valid & (arr == cls)).sum() / n), 4) if n else np.nan})

    for y in years:
        for source, stem in (("ours", "lulc"), ("ours_smoothed", "lulc_smooth")):
            p = OUT_DIR / f"{stem}_{y}.tif"
            if p.exists():
                with rasterio.open(p) as src:
                    add(source, y, src.read(1))
    for kind, yrs in (("worldcover", (2020, 2021)), ("io", range(2017, 2024))):
        for y in yrs:
            if ref_path(kind, y).exists():
                add(kind, y, to30(kind, y)[0])
    df = pd.DataFrame(rows)
    df.to_csv(SHARES_CSV, index=False)
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", default="all", choices=["refs", "train", "predict", "smooth", "shares", "all"])
    ap.add_argument("--years", default="2015-2026")
    args = ap.parse_args()
    a, b = (int(x) for x in args.years.split("-"))
    years = range(a, b + 1)
    if args.step in ("refs", "all"):
        t0 = timing.start("land-cover references", "WorldCover 2020–2021, Impact Observatory 2017–2023")
        notes = []
        for kind, yrs in (("worldcover", (2020, 2021)), ("io", range(2017, 2024))):
            for y in yrs:
                if not ref_path(kind, y).exists():
                    notes.append(fetch_ref(kind, y))
        timing.done("land-cover references", t0, "; ".join(notes) or "cached")
    if args.step in ("train", "all"):
        t0 = timing.start("land-cover classifier", "random forest on stable WorldCover 2020–2021 cells")
        acc = train()
        oa = acc.loc[acc.metric == "overall_accuracy", "value"].squeeze()
        timing.done("land-cover classifier", t0, f"blocked CV overall accuracy {oa}")
        print(acc.to_string(index=False))
    if args.step in ("predict", "all"):
        model = joblib.load(MODEL)
        for y in years:
            t0 = timing.start(f"land cover {y}")
            timing.done(f"land cover {y}", t0, predict(y, model).split("/")[-1])
    if args.step in ("smooth", "all"):
        t0 = timing.start("land cover smoothing", "three-year mean of class probabilities")
        timing.done("land cover smoothing", t0, f"{len(smooth(years))} years")
    if args.step in ("shares", "all"):
        df = shares(years)
        piv = df[(df.zone == "metro") & (df["class"] == "Built-up")].pivot(index="year", columns="source", values="share")
        print(piv.round(3).to_string())


if __name__ == "__main__":
    main()
