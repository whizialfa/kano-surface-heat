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

## Preliminary (hot season 2026, 6 scenes)

Ring median 45.0 °C, outline median 43.5 °C: a daytime **surface cool island**. Ungogo hottest LGA (44.3 °C mean), Kano Municipal and Gwale coolest (42.6). The bright line in Fagge is the airport runway. Do not quote as the result until the 2015–2026 series and the composition classes are in.

## Do not

- Commit rasters, WorldCover tiles or the anchor's supplement
- Mix the metro headline with any tighter map crop without saying so
- Put this analysis in `~/paper-replications` or inside `15-min-cities-nigeria`
- Rename the GitHub slug once it is public
