"""Chart plates in the same furniture family as 15-min-cities-nigeria."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from matplotlib.ticker import MultipleLocator

from .paths import CHARTS, DATA_PROCESSED

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
for _p in (ARIAL, ARIAL_BOLD):
    font_manager.fontManager.addfont(_p)
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["axes.unicode_minus"] = False

PAGE = "#ffffff"
LAND = "#f8f1e7"
INK = "#000000"
GRID = "#dfcfbf"
CREDIT = "©Wisdom Akpabio"
STROKE = 1.15
HALO = [pe.withStroke(linewidth=3.0, foreground=PAGE)]
SMALL_HALO = [pe.withStroke(linewidth=2.2, foreground=PAGE)]

# Same hues as the plates: built-up is the land-cover plate's dull red, farmland its ochre.
BUILT = "#9e4c42"
BARE = "#c8952e"
GREEN = "#5d7a3a"
FRINGE = "#b0562c"
CITY = "#2f5d7c"
HOT_SEASON = "#b0562c"
HARMATTAN = "#d9a441"
WET = "#2f5d7c"


def _fp(bold: bool, size: float) -> FontProperties:
    return FontProperties(fname=ARIAL_BOLD if bold else ARIAL, size=size)


def _text_frac(text: str, size: float, *, fig_w: float = 15.0, pad_in: float = 0.50) -> float:
    em = size / 72.0
    return (pad_in + len(text) * em * 0.56) / fig_w


def _open_plate(title: str, subtitle: str, footnote: str):
    fig_w, fig_h = 15.0, 9.2
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=PAGE, dpi=200)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    mx, my = 0.022, 0.036
    fig.patches.append(Rectangle((mx, my), 1 - 2 * mx, 1 - 2 * my, transform=fig.transFigure,
                                 facecolor="none", edgecolor=INK, linewidth=STROKE, zorder=30, clip_on=False))

    title_w = min(max(max(_text_frac(title, 15), _text_frac(subtitle, 13)), 0.26), 0.50)
    title_h = 0.100
    tx, ty = mx, 1 - my - title_h
    fig.patches.append(Rectangle((tx, ty), title_w, title_h, transform=fig.transFigure, facecolor=PAGE,
                                 edgecolor=INK, linewidth=STROKE, zorder=31, clip_on=False))
    fig.text(tx + 0.5 * title_w, ty + 0.64 * title_h, title, ha="center", va="center",
             fontproperties=_fp(True, 15), color=INK, zorder=32)
    fig.text(tx + 0.5 * title_w, ty + 0.28 * title_h, subtitle, ha="center", va="center",
             fontproperties=_fp(True, 13), color=INK, zorder=32)

    lines = [ln.strip() for ln in footnote.split("\n") if ln.strip()]
    note_w = min(max(max(_text_frac(ln, 12, pad_in=0.55) for ln in lines), 0.40), 0.66)
    note_h = 0.100
    nx, ny = 0.5 - 0.5 * note_w, my
    fig.patches.append(Rectangle((nx, ny), note_w, note_h, transform=fig.transFigure, facecolor=PAGE,
                                 edgecolor=INK, linewidth=STROKE, zorder=31, clip_on=False))
    fig.text(nx + 0.5 * note_w, ny + 0.5 * note_h, footnote, ha="center", va="center",
             fontproperties=_fp(True, 12), color=INK, zorder=32, linespacing=1.35)
    fig.text(1 - mx - 0.012, my + 0.012, CREDIT, ha="right", va="bottom", fontproperties=_fp(False, 8),
             color=INK, zorder=32, path_effects=SMALL_HALO)

    ax = fig.add_axes([0.090, 0.248, 0.862, 0.568])
    ax.set_facecolor(LAND)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK)
        ax.spines[side].set_linewidth(0.9)
    ax.tick_params(colors=INK, labelsize=11, width=0.8, length=4)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    return fig, ax


def _ticks(ax):
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(_fp(False, 11))


def _labels(ax, xlabel: str, ylabel: str) -> None:
    ax.set_xlabel(xlabel, fontproperties=_fp(False, 12), color=INK, labelpad=8)
    ax.set_ylabel(ylabel, fontproperties=_fp(False, 12), color=INK, labelpad=8)


def _end_label(ax, x, y, text, color, dy=0):
    ax.annotate(text, (x, y), xytext=(10, dy), textcoords="offset points", ha="left", va="center",
                fontproperties=_fp(True, 12), color=color, path_effects=HALO, zorder=5)


def _save(fig, name: str) -> str:
    CHARTS.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(CHARTS / f"{name}.{ext}", facecolor=PAGE)
    plt.close(fig)
    return str(CHARTS / f"{name}.png")


def built_cells_cool() -> str:
    g = pd.read_csv(DATA_PROCESSED / "composition_gradient.csv")
    s = g[g["variant"] == "sahel"].pivot(index="cells_of_9", columns="group", values="lst_mean")
    fig, ax = _open_plate(
        "THE BUILT CITY IS THE COOL GROUND",
        "Hot-season surface temperature in metro Kano",
        "Each point averages every 30 m cell with that many built-up, bare or green 10 m cells out of nine.\n"
        "Built-up cells cool the ground. Farmland and bare earth heat it. Trees and grass barely move it.\n"
        "Ground, not air: median of 40 clear Landsat scenes, March to May, 2015 to 2026.",
    )
    x = s.index.to_numpy()
    series = (("urban", BUILT, "Built-up", 0), ("bare", BARE, "Farmland and bare earth", 0),
              ("vegetation", GREEN, "Trees, shrub and grass", 0))
    for col, color, label, dy in series:
        ax.plot(x, s[col], color=color, lw=2.6, marker="o", ms=6, zorder=4)
        _end_label(ax, x[-1], s[col].iloc[-1], label, color, dy)
    ax.set_xlim(-0.3, 11.6)
    ax.set_xticks(range(10))
    lo = np.floor(np.nanmin(s[["urban", "bare", "vegetation"]].to_numpy()) - 0.3)
    hi = np.ceil(np.nanmax(s[["urban", "bare", "vegetation"]].to_numpy()) + 0.3)
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    _labels(ax, "10 m cells of that cover, out of the nine inside one 30 m cell", "Surface temperature, °C")
    _ticks(ax)
    return _save(fig, "built_cells_cool")


def cool_island_by_year() -> str:
    df = pd.read_csv(DATA_PROCESSED / "lst_series.csv").sort_values("year")
    fig, ax = _open_plate(
        "COOLER THAN ITS FARMLAND",
        "Kano against the country around it, each hot season",
        "Below zero, the city's ground is cooler than the farmland 1 to 10 km outside it.\n"
        "Above zero, the new fringe of Ungogo and Kumbotso is hotter than the old city.\n"
        "Median of clear Landsat scenes, March to May. One to six scenes a year.",
    )
    x = df["year"].to_numpy()
    w = 0.38
    ax.bar(x - w / 2, df["suhi_median"], width=w, color=CITY, zorder=3)
    ax.bar(x + w / 2, df["fringe_minus_core"], width=w, color=FRINGE, zorder=3)
    ax.axhline(0, color=INK, lw=0.9, zorder=4)
    ax.set_xticks(x)
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    ax.set_ylim(-2.8, 2.8)
    ax.text(x[0] - 0.5, -2.55, "City minus rural ring", color=CITY, fontproperties=_fp(True, 12),
            path_effects=HALO, va="center")
    ax.text(x[0] - 0.5, 2.55, "Fringe minus old city", color=FRINGE, fontproperties=_fp(True, 12),
            path_effects=HALO, va="center")
    _labels(ax, "Hot season", "Difference in surface temperature, °C")
    _ticks(ax)
    return _save(fig, "cool_island_by_year")


def cool_day_warm_night() -> str:
    s = pd.read_csv(DATA_PROCESSED / "modis_summary.csv")
    order = ("Terra 10:30", "Aqua 13:30", "Terra 22:30", "Aqua 01:30")
    ticks = ("10:30", "13:30", "22:30", "01:30")
    seasons = (("hot", "Hot season, March to May", HOT_SEASON),
               ("harmattan", "Harmattan, November to February", HARMATTAN),
               ("wet", "Wet season, June to September", WET))
    fig, ax = _open_plate(
        "COOL BY DAY, WARM BY NIGHT",
        "Kano against the farmland around it",
        "Below zero, the city's ground is cooler than the farmland 1 to 10 km outside it.\n"
        "In the dry seasons the city is cooler by day and warmer by night. In the rains it is warmer by day.\n"
        "MODIS 8-day clear-sky composites, 1 km, 2015 to 2026. Ground, not air.",
    )
    x = np.arange(len(order))
    w = 0.26
    for k, (season, label, color) in enumerate(seasons):
        vals = [s[(s["season"] == season) & (s["overpass"] == op)]["city_minus_ring_median"].squeeze() for op in order]
        ax.bar(x + (k - 1) * w, vals, width=w, color=color, zorder=3, label=label)
    ax.axhline(0, color=INK, lw=0.9, zorder=4)
    ax.axvspan(1.5, 3.5, color="#2b1d16", alpha=0.08, zorder=1)
    ax.text(0.5, 2.25, "Day", ha="center", fontproperties=_fp(True, 12), color=INK)
    ax.text(2.5, 2.25, "Night", ha="center", fontproperties=_fp(True, 12), color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(ticks)
    ax.set_xlim(-0.6, 3.6)
    ax.set_ylim(-1.0, 2.5)
    ax.yaxis.set_major_locator(MultipleLocator(0.5))
    leg = ax.legend(loc="upper left", frameon=False, prop=_fp(False, 11))
    for text, (_, _, color) in zip(leg.get_texts(), seasons):
        text.set_color(color)
    _labels(ax, "Satellite pass, local time", "City minus rural ring, °C")
    _ticks(ax)
    return _save(fig, "cool_day_warm_night")


def main() -> None:
    print(built_cells_cool())
    print(cool_island_by_year())
    print(cool_day_warm_night())


if __name__ == "__main__":
    main()
