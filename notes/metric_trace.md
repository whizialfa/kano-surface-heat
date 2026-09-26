# Metric trace

Anchor: Ramachandra, T. V., Rana, R. S., Vinay, S. & Aithal, B. H. (2025). Urban heat island linkages with the landscape morphology. *Scientific Reports* 15, 24485. https://doi.org/10.1038/s41598-025-09141-5. Supplement (tables S1–S4) is in `references/ramachandra2025_supplement.docx`.

**This is an adapted measurement, not a clone.** Bangalore is a humid upland city on one April 2022 scene. Kano is a semi-arid Sahelian city surrounded by bare dry-season farmland. The anchor's own limitations (single date, no in-situ validation, no people) are the parts we change on purpose.

## What the anchor reports, and how each number is made

| Quoted number | Value (Bangalore) | Raw input | Transformation |
|---|---|---|---|
| Mean LST | 38.61 °C (29.86–48.00) | Landsat 8 TIRS band 10, April 2022, <5% cloud | DN → TOA radiance → brightness temperature → NDVI-based emissivity (ε = 0.004·Pv + 0.986) → LST. No atmospheric correction |
| LST by land-use mix | C1 all bare 39.92 °C, C2 all urban 39.74, C3 39.57, C4 39.42 … water lowest | Sentinel-2 10 m, Random Forest with field GPS training (4 classes) | Count the nine 10 m cells inside each 30 m LST pixel, assign one of 12 composition classes (table S2), mean LST per class |
| Bivariate r with LST | NDVI −0.46, MNDWI −0.23, BSI +0.65, NDBI +0.69 | Landsat 8 reflectance bands | 1,000 random points, simple regression |
| Multivariate model | LST = 38.16 + 2.54·NDBI − 5.36·NDVI − 8.60·MNDWI + 6.73·BSI | same | OLS on the same points |
| Hot / cold spots | > 44.53 °C (15.41 km²), < 35.08 °C (23.85 km²) | LST | Stated rule μ ± 2σ |
| UTFVI unfavourable | 545 km² (76%) vs favourable 169 km² | LST | UTFVI = (LST − T_mean)/T_mean, six classes from table S4 |
| Policy line | keep ≥ 30% vegetation (C6) per plot | composition classes | reading of the class means |

## What breaks in Kano, and what we do instead

1. **Single date.** The anchor says so itself. We use a per-pixel **median of all clear scenes** in each season and year, scored on the city, not the whole scene (`scenes.py`: coverage ≥ 98% of the outline and ≥ 98% of those pixels clear in QA_PIXEL). Headline season is **hot dry, March–May**, which matches the anchor's April. Harmattan (Nov–Feb) and wet (Jun–Sep) are comparisons.
2. **LST retrieval.** We use USGS Collection 2 Level-2 surface temperature (`ST_B10`, single-channel algorithm, ASTER GED emissivity, atmospheric correction), scale 0.00341802, offset 149.0 K. It is more defensible than the anchor's uncorrected mono-window and it is the published USGS product. Consequence: our absolute °C are not directly comparable to theirs. Rankings and contrasts are.
3. **Land-use map.** No field training data. We use **ESA WorldCover 10 m (2021)** from Planetary Computer, collapsed to the anchor's four classes: built-up → urban; bare/sparse → bare; tree, shrub, grassland, cropland, mangrove, moss → vegetation; water and wetland → water. Cropland in the dry season is bare earth to the thermal sensor; we report the composition with cropland as vegetation (anchor-faithful) and as bare (Sahel-faithful), and say which one we quote.
4. **Composition classes overlap and leave gaps.** Table S2 is not a partition: a 9-cell pixel can satisfy two classes or none. We assign in order C1, C2, C11, C12, then C3–C10, first match wins, and count the unassigned share. That share is reported, never dropped.
5. **Hot and cold spot thresholds.** The anchor's numbers (44.53 and 35.08 around a mean of 38.61) are not symmetric, so they did not come from their own μ ± 2σ rule, and equation 16 has a sign typo. We use μ + 2σ and μ − 2σ of the outline's LST, both stated.
6. **UTFVI thresholds** in table S4 are equal-interval breaks of Bangalore's own index range (step 0.0946), computed in °C. They do not transfer. We compute UTFVI in **kelvin** with the widely used Zhang et al. ecological classes (< 0, 0–0.005, 0.005–0.010, 0.010–0.015, 0.015–0.020, > 0.020) and report the Bangalore-style equal-interval split as a sensitivity only.
7. **Spectral indices** come from the same Landsat scene (co-registered, same date). Regressions use 1,000 random points as in the anchor, then all pixels, and we report Moran's I on residuals. Spatial autocorrelation makes the anchor's p-values optimistic; coefficients are the result, p-values are not.
8. **Boundary.** Kano metropolitan area, eight LGAs, 573 km² (`kano_study_boundary.gpkg`, shared with `15-min-cities-nigeria`). A 5–10 km rural ring outside the outline is the reference for surface heat-island intensity, which the anchor never measured.

## What we add that the anchor does not have

- **People.** GRID3 / WorldPop NGA v3.0 population and age-sex rasters on the same 200 m hexes as the walking paper: total, under-5, over-65, women 15–49, inside hot spots and the hottest decile.
- **Wards and named places.** Every quoted hot or cool area gets a ward and a GRID3 settlement name.
- **Time.** Hot-season medians for 2014–2026, so the story can say whether the fringe is warming as it builds out.

## Hypothesis to test, not a result

In semi-arid cities the bare farmland around the city is often hotter by day than the built-up core in the dry season, a *surface urban cool island*. The anchor already found bare soil (C1) slightly hotter than pure urban (C2) in humid Bangalore. If Kano's fringe of Ungogo and Kumbotso is hotter than the walled city, the finding is not "the city is a heat island". It is that the new fringe is the hot ground, and that is where the later population moved.

## Data vintage

- Landsat 8/9 Collection 2 Level-2, 2014–2026, Microsoft Planetary Computer (`landsat-c2-l2`)
- ESA WorldCover v200 (2021), Planetary Computer (`esa-worldcover`)
- GRID3 NGA population v3.0 (NMEP 2022–23 scaled to UN WPP July 2025) and v3.0 age-sex
- GRID3 wards and settlements; Kano metro outline from `15-min-cities-nigeria`
