---
name: kano-heat
description: >-
  Adapts Ramachandra et al. 2025 (Sci Rep) surface heat and land-use composition
  analysis to metropolitan Kano with Landsat C2 L2 surface temperature, ESA
  WorldCover and GRID3 age-sex population. Not a replication. Use when working on
  Kano LST, surface heat island or cool island, UTFVI, hot spots, C1–C12
  composition classes, heat exposure of under-5s and over-65s, or this repo's plates.
---

# Kano surface heat (adaptation)

## Default stance

Adapted measurement of Ramachandra, Rana, Vinay & Aithal 2025, *Sci Rep* 15, 24485. Never call it a replication. The trace and every departure live in `notes/metric_trace.md`; update it when a method changes.

- Study area is the Kano metro outline shared with `15-min-cities-nigeria` (eight LGAs, 573 km²). Copy it with `kanoheat.inputs`, do not redraw it.
- Rural reference ring is 1–10 km outside the outline.
- Headline season is **hot, March–May**. Quote the season and the number of scenes with every temperature.
- LST is USGS C2 L2 `ST_B10` (× 0.00341802 + 149.0 K). Do not recompute the anchor's uncorrected mono-window as the headline.
- Scenes must cover ≥ 98% of the outline and have ≥ 98% of it clear in QA_PIXEL. Whole-scene `eo:cloud_cover` is not a city filter.
- One footprint, WRS-2 188/052, covers the city. The others clip it.
- Say "hottest ground", not "hottest air". Land surface temperature is not air temperature.

## Standing choices

- Composition classes follow table S2 of the anchor, assigned first match in order C1, C2, C11, C12, C3–C10. Report the unassigned share; never drop it.
- Dry-season cropland is bare to the thermal sensor. Run composition with cropland as vegetation (anchor-faithful) and as bare; say which is quoted.
- Hot and cold spots are μ ± 2σ of the outline LST. The anchor's published thresholds do not follow its own rule.
- UTFVI is computed in kelvin with the Zhang et al. classes. The anchor's table S4 breaks are Bangalore-specific and are a sensitivity only.
- Regression p-values are not results under spatial autocorrelation. Quote coefficients and Moran's I of residuals.
- People come from GRID3 NGA v3.0 total and age-sex rasters on the 200 m hexes.

## Quoted headlines (hot season, 2015–2026)

Mast: **Hot ground** / *Surface heat, land cover and people in metropolitan Kano*. Write-up `notes/results.md`.

- **Surface cool island.** All 28 March–April scenes: city cooler than the 1–10 km ring (median −1.6 °C) and fringe (Ungogo, Kumbotso) hotter than the old city (median +1.75 °C). 37/40 and 38/40 across March–May; every exception is a May scene after early rain (4 May 2019 is +4.3 °C). Lead with per-scene counts (`lst_by_scene.csv`), not yearly medians.
- **Built-up is cool ground.** Gradient (`composition_gradient.csv`): built 0→9 cells 47.00→44.75 °C; farmland/bare 44.95→47.39; trees/shrub/grass flat ~45.9. Anchor classes: C11 all-vegetation hottest (47.11) with cropland as vegetation; C1 all-bare hottest (47.39) with cropland as bare; C2 built 44.75 either way.
- **NDVI does not predict heat** (r −0.04 to +0.20 by year; Bangalore −0.46). MNDWI strongest (−0.62). Never quote the four-index model: VIF up to 34, signs flip by year, Moran's I 0.30–0.67.
- **Hot spots** (μ+2σ = 49.8 °C) 1.7 km², 1,854 of 1,922 pixels cropland or grass; Fanisau, Rangaza, Karo and Kwachiri (airport). UTFVI "strong" or worse 1.7% (kelvin, Zhang); UTFVI is relative to each city's mean, so do not compare shares with Bangalore's 76% as if they meant the same thing.
- **People.** Population-weighted LST 45.0 vs area 46.0 °C. Hottest tenth of populated hexes: 122k people (2.1%). Hot and far (hottest fifth of hexes with ≥ 50 people, and PT_k > 15 min): 261k people, 42k under five, 95% of everyone on the hottest fifth; only 25 of 831 hot hexes are within 15 min. Always use the ≥ 50-people definition so the plate and the prose agree. r(LST, walk) = 0.36. Hottest wards Karo, Yada Kunya, Chalawa, Rangaza, Fanisau; Dan Maliki and Naibawa in Kumbotso are cool.
- **Age-sex layers are one age structure across Kano** (under-5 16.5–16.7% of every LGA). Report age counts, never age-weighted temperatures.

## Do not

- Commit rasters, WorldCover tiles or the anchor's supplement
- Mix the metro headline with any tighter map crop without saying so
- Put this analysis in `~/paper-replications` or inside `15-min-cities-nigeria`
- Rename the GitHub slug once it is public
