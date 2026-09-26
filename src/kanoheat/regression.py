"""LST against NDVI, NDBI, MNDWI and BSI (anchor Fig. 5 and Eq. 3).

Anchor-faithful fit: 1,000 random pixels inside the outline, bivariate r and
OLS. Added: the same model on every pixel, variance inflation factors, and
Moran's I of the 1,000-point residuals, because neighbouring pixels are not
independent and the anchor's p-values assume they are.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import rasterio
import statsmodels.api as sm
from esda.moran import Moran
from libpysal.weights import KNN
from statsmodels.stats.outliers_influence import variance_inflation_factor

from . import timing
from .composition import inside_mask
from .indices import NAMES
from .lst import LST_DIR, grid
from .paths import DATA_PROCESSED, UTM

REGRESSION_CSV = DATA_PROCESSED / "regression.csv"
INDEX_DIR = LST_DIR.parent / "indices"
SEED = 42
N_POINTS = 1_000


def pool_indices(season: str = "hot") -> str:
    paths = sorted(INDEX_DIR.glob(f"indices_{season}_20*.tif"))
    stack = []
    for p in paths:
        with rasterio.open(p) as src:
            stack.append(src.read())
    arr = np.nanmedian(np.stack(stack), axis=0).astype("float32")
    transform, width, height = grid()
    out = INDEX_DIR / f"indices_{season}_all.tif"
    with rasterio.open(out, "w", driver="GTiff", width=width, height=height, count=4, dtype="float32",
                       crs=f"EPSG:{UTM}", transform=transform, nodata=np.nan, compress="deflate",
                       tiled=True) as dst:
        dst.write(arr)
    return str(out)


def load(tag: str):
    with rasterio.open(LST_DIR / f"lst_{tag}.tif") as src:
        lst = src.read(1)
    with rasterio.open(INDEX_DIR / f"indices_{tag}.tif") as src:
        idx = src.read()
    return lst, idx


def fit(tag: str) -> list[dict]:
    lst, idx = load(tag)
    transform, _, _ = grid()
    inside = inside_mask()
    ok = inside & np.isfinite(lst) & np.all(np.isfinite(idx), axis=0)
    rows_i, cols_i = np.nonzero(ok)
    y_all = lst[ok].astype("float64")
    X_all = np.column_stack([idx[k][ok] for k in range(4)]).astype("float64")
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(y_all), size=min(N_POINTS, len(y_all)), replace=False)
    out = []

    for sample, y, X, rr, cc in (
        ("points_1000", y_all[pick], X_all[pick], rows_i[pick], cols_i[pick]),
        ("all_pixels", y_all, X_all, None, None),
    ):
        for k, name in enumerate(NAMES):
            r = float(np.corrcoef(X[:, k], y)[0, 1])
            out.append({"tag": tag, "sample": sample, "model": "bivariate", "term": name, "coef": np.nan,
                        "r": round(r, 3), "r2": round(r * r, 3), "n": len(y)})
        Xc = sm.add_constant(pd.DataFrame(X, columns=NAMES))
        res = sm.OLS(y, Xc).fit()
        vif = {name: variance_inflation_factor(Xc.values, i) for i, name in enumerate(Xc.columns) if name != "const"}
        moran_i = moran_p = np.nan
        if rr is not None:
            xs = transform.c + (cc + 0.5) * transform.a
            ys = transform.f + (rr + 0.5) * transform.e
            w = KNN.from_array(np.c_[xs, ys], k=8)
            w.transform = "r"
            mi = Moran(res.resid, w, permutations=999)
            moran_i, moran_p = float(mi.I), float(mi.p_sim)
        for term in Xc.columns:
            out.append({
                "tag": tag, "sample": sample, "model": "multivariate", "term": term,
                "coef": round(float(res.params[term]), 3),
                "p": float(res.pvalues[term]),
                "vif": round(float(vif.get(term, np.nan)), 2),
                "r2": round(float(res.rsquared), 3), "n": len(y),
                "moran_I_resid": round(moran_i, 3) if np.isfinite(moran_i) else np.nan,
                "moran_p": moran_p,
            })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="hot")
    args = ap.parse_args()
    t0 = timing.start("regression", "LST ~ NDVI + NDBI + MNDWI + BSI")
    pool_indices(args.season)
    tags = sorted(p.stem.replace("indices_", "") for p in INDEX_DIR.glob(f"indices_{args.season}_*.tif"))
    rows = []
    for tag in tags:
        if (LST_DIR / f"lst_{tag}.tif").exists():
            rows.extend(fit(tag))
    df = pd.DataFrame(rows)
    df.to_csv(REGRESSION_CSV, index=False)
    timing.done("regression", t0, f"{len(tags)} season-years → {REGRESSION_CSV.name}")
    show = df[df["tag"].isin([f"{args.season}_all", f"{args.season}_2026"])]
    with pd.option_context("display.width", 200):
        print(show.to_string(index=False))


if __name__ == "__main__":
    main()
