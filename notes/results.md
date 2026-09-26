---
title: "Hot ground"
subtitle: "Surface heat, land cover and people in metropolitan Kano"
author: Wisdom Akpabio
date: September 2026
---

# Summary

In the hot dry season, metropolitan Kano is cooler than the farmland around it. In all 28 clear Landsat scenes from March and April between 2015 and 2026, the city's median surface was cooler than a ring 1 to 10 km outside it, by 1.6 °C at the median (0.3 to 2.9 °C). In the same 28 scenes the new fringe in Ungogo and Kumbotso was hotter than the old city, by 1.75 °C at the median. The pattern weakens in May, when early storms wet the fields; the three scenes that break it are all May scenes.

Built-up ground is Kano's cool ground. Every additional built-up 10 m cell in a 30 m pixel lowers its hot-season surface temperature, from 47.0 °C with none to 44.8 °C with all nine. Every additional cell of farmland or bare earth raises it, from 45.0 to 47.4 °C. Trees, shrub and grass barely change it. This reverses the ordering in Bangalore, the anchor city, where vegetation and water were the heat sinks and the policy advice was to keep 30% green cover per plot. Greenness (NDVI) has no relationship with hot-season surface heat in Kano in any year.

People live on the cooler ground. The population-weighted surface temperature is 45.0 °C, a full degree below the average hexagon (46.0 °C). The hottest tenth of populated hexagons holds 122,000 people (2.1%); the coolest tenth holds 616,000. The heat that does reach homes sits on the farmland edge: Karo, Yada Kunya, Rangaza and Fanisau in Ungogo, and Chalawa in Kumbotso. 268,000 people, 44,000 of them under five, live on the hottest fifth of ground and more than 15 minutes' walk from five clinics and five schools. Hotter hexagons are farther from services (population-weighted r = 0.36).

This is surface temperature, not air temperature. A cool roof is not a cool bedroom. The claim is about where the ground is hottest and what covers it.

# 1. Question and anchor

Ramachandra, Rana, Vinay and Aithal (2025) link land surface temperature (LST) to the land-use mix inside each 30 m Landsat pixel in Bangalore, using one April 2022 scene, a 10 m Sentinel-2 land-use map and four spectral indices. They find bare soil and urban pixels hottest (39.9 and 39.7 °C), vegetation and water coolest, and recommend at least 30% vegetation per plot.

This paper asks the same question of Kano, a semi-arid Sahelian city ringed by dry-season farmland, and adds what the anchor lacks: many dates, people, wards and walking time. **It is an adapted measurement, not a replication.** Every departure is listed in `notes/metric_trace.md`.

# 2. Data and method

**Study area.** Kano metropolitan area: eight local government areas, 573 km², 5.78 million people (GRID3 NGA v3.0, scaled to July 2025). The outline, wards, 200 m hexagons and named settlements are shared with *Fifteen minutes on foot*. A ring 1 to 10 km outside the outline is the rural reference.

**Surface temperature.** Landsat 8 and 9 Collection 2 Level-2 surface temperature (USGS single-channel algorithm, atmospherically corrected, ASTER emissivity), from Microsoft Planetary Computer. Of 1,160 scenes searched, 142 cover at least 98% of the outline with at least 98% of those pixels clear in the QA band; one footprint (WRS-2 path 188, row 52) covers the whole city. The hot season is March to May: 40 scenes, one to six a year. Each year's surface is the per-pixel median of its scenes; the pooled surface is the median of the twelve yearly medians.

**Land-use mix.** ESA WorldCover 10 m (2021), warped onto a 10 m grid that nests exactly three by three inside the 30 m LST grid, and collapsed to the anchor's four groups: built-up, bare, vegetation, water. Dry-season cropland is bare earth to a thermal sensor, so the analysis is run twice: cropland as vegetation (the anchor's rule) and cropland as bare. The anchor's twelve composition classes (its table S2) overlap and leave gaps; we assign them in a fixed order and report the unassigned share. Because the table is ambiguous, the main land-use result is a gradient that needs no classes.

**Spectral indices.** NDVI, NDBI, MNDWI and the bare-soil index from the same scenes, medians per season. As in the anchor: 1,000 random pixels, simple correlations and a four-index linear model; added: the same model on all 636,483 pixels, variance inflation factors and Moran's I of the residuals.

**People and walking.** Hexagon population from GRID3 v3.0; under-5, over-65 and women 15 to 49 from the v3.0 age-sex layers. Each hexagon carries its dual-access walking time to five clinics and five schools (PT_k) from the walking paper.

# 3. Results

## 3.1 A city cooler than its fields

| | Scenes | City cooler than ring | Median city minus ring | Fringe hotter than old city | Median fringe minus old city |
|---|---|---|---|---|---|
| March and April | 28 | 28 | −1.6 °C | 28 | +1.75 °C |
| May | 12 | 9 | −1.0 °C | 10 | +1.3 °C |
| All hot season | 40 | 37 | −1.5 °C | 38 | +1.6 °C |

*Old city: Kano Municipal, Dala, Gwale, Fagge, Nassarawa, Tarauni. Fringe: Ungogo, Kumbotso. Source: `lst_by_scene.csv`.*

The three scenes where the city is warmer than its ring are 1 May 2018 (+0.05 °C), 4 May 2019 (+4.3 °C) and 28 May 2025 (+1.7 °C). On 4 May 2019 the ring fell to 42.4 °C while the city held 46.7 °C, the signature of wet fields after an early storm. That one scene carries the only positive yearly median in the series (Figure 2).

Across the pooled surface, local government medians run from Kano Municipal (44.0 °C) and Gwale (44.2) to Fagge (45.8) and Ungogo (46.9). Hot spots (above the city mean plus two standard deviations, 49.8 °C) cover 1.7 km², and 1,854 of their 1,922 pixels are cropland or grass, not buildings: Fanisau, Rangaza and Karo in Ungogo, and Kwachiri in Fagge, the ward that contains Mallam Aminu Kano International Airport and its runway. Cold spots (below 42.2 °C) cover 14.3 km², along the Challawa river and the dense southern wards of Panshekara, Naibawa, Dorayi and Kumbotso.

## 3.2 What covers the hot ground

| Composition class | Bangalore | Kano, cropland as vegetation | Kano, cropland as bare |
|---|---|---|---|
| C1, all bare | 39.92 °C | 44.67 °C (0.7%) | **47.39 °C (34.5%)** |
| C2, all built-up | 39.74 °C | **44.75 °C (38.0%)** | **44.75 °C (38.0%)** |
| C11, all vegetation | cool | **47.11 °C (47.2%)** | 45.85 °C (6.5%) |
| C12, all water | coolest | 39.08 °C (0.05%) | 39.08 °C (0.05%) |
| Unassigned | not reported | 4.0% | 5.5% |

*Mean hot-season LST, pooled 2015 to 2026. Share of the city's pixels in brackets. Source: `composition_lst.csv`.*

Read the anchor's way, Kano's all-vegetation pixels are its hottest ground, because most of what WorldCover calls vegetation is cropland that is bare in March. Read the Sahel's way, bare ground is hottest, as in Bangalore, but pure built-up pixels are still 1.1 °C cooler than the remaining trees, shrub and grass, and 2.6 °C cooler than bare fields. Only open water is cooler than the built city.

The gradient (Figure 1, `composition_gradient.csv`) shows the same thing without classes:

| 10 m cells out of nine | 0 | 3 | 6 | 9 |
|---|---|---|---|---|
| Built-up | 47.00 | 45.94 | 45.67 | 44.75 |
| Farmland and bare earth | 44.95 | 46.21 | 46.41 | 47.39 |
| Trees, shrub and grass | 46.01 | 45.94 | 45.92 | 45.85 |

## 3.3 Greenness does not predict heat here

| Correlation with LST, all pixels | NDVI | NDBI | MNDWI | Bare-soil index |
|---|---|---|---|---|
| Bangalore (anchor) | −0.46 | +0.69 | −0.23 | +0.65 |
| Kano, pooled hot season | +0.15 | +0.48 | −0.62 | +0.53 |
| Kano, range over 12 years | −0.04 to +0.20 | +0.26 to +0.52 | −0.21 to −0.64 | +0.23 to +0.58 |

Moisture, not greenness, tracks the cool ground: the water index is the strongest single correlate in every year. The anchor's four-index equation does not transfer. The indices are collinear (variance inflation up to 34), the fitted coefficients change sign between years (the bare-soil term runs from +12 to −87), the model explains about half the variance (R² 0.50 pooled) and its residuals are strongly clustered in space (Moran's I 0.30 to 0.67). We report the simple correlations and not the model. Source: `regression.csv`.

## 3.4 Who lives on the hot ground

| | People | Under 5 | Over 65 |
|---|---|---|---|
| Whole city | 5,780,865 | | |
| Hottest tenth of populated hexagons (≥ 47.7 °C) | 122,404 (2.1%) | 20,529 | 2,675 |
| Coolest tenth (≤ 43.6 °C) | 616,189 (10.7%) | 104,972 | 13,676 |
| Hottest fifth (≥ 47.1 °C) and more than 15 minutes' walk | 267,879 | 44,124 | |

*Populated: at least 50 people in the hexagon. Source: `exposure_summary.csv`.*

The GRID3 age-sex layers apply one age structure across the city: under-fives are 16.5 to 16.7% of every local government area and over-65s 2.2%. They convert people into counts of children and elders, but they cannot show whether children live on hotter ground than adults. We give counts and never an age-weighted temperature.

| Ward | LGA | People | LST, population-weighted | Walk, population-weighted | Largest named place |
|---|---|---|---|---|---|
| Karo | Ungogo | 20,919 | 47.9 °C | 31 min | Muncika Kudu |
| Yada Kunya | Ungogo | 51,646 | 47.4 °C | 25 min | Layin Kasuwa |
| Chalawa | Kumbotso | 39,604 | 47.1 °C | 36 min | Kusuba Kwari |
| Rangaza | Ungogo | 114,696 | 46.9 °C | 21 min | Layin Masallacin Juma'a |
| Fanisau | Ungogo | 48,494 | 46.1 °C | 23 min | Kan Fako |
| Dan Maliki | Kumbotso | 264,515 | 43.9 °C | 11 min | Gidan Leda |
| Daurawa | Tarauni | 17,024 | 43.8 °C | 8 min | Layin Barwa |

*Hottest five wards and two of the coolest. Source: `ward_heat.csv`.*

Kumbotso is not uniformly hot. Its dense inner wards, Dan Maliki and Naibawa, are among the coolest ground in the city. The heat is where farmland still meets new building.

# 4. Discussion

Kano behaves like other dry cities: by day in the dry season its built fabric is cooler than the bare fields around it. Earth and cement compounds, narrow shaded lanes, courtyard trees and irrigated gardens along the rivers all keep the surface below that of open, sunlit, dry soil. The anchor's advice, more vegetation per plot, is right for Bangalore and weak for Kano in March: what cools here is shade and moisture, not greenness as a satellite measures it.

The finding that matters for planning is the edge. Kano's growth in Ungogo and Kumbotso is building onto the hottest ground in the metropolitan area, and the people already there are the ones farthest from clinics and schools. The walking paper found the later population living in Ungogo and Kumbotso while services stayed in the old city. This paper adds that the same families are on the hottest ground.

# 5. Limits

- Land surface temperature is not air temperature or heat stress. There is no humidity, wind or night-time signal here; Landsat passes at about 10:30 local time.
- The land-use map is from 2021 and the surface series runs to 2026. Fringe land that was farmland in 2021 may now be built.
- WorldCover's vegetation and cropland classes are not a field survey, and the anchor's composition table is ambiguous; the gradient is the robust version.
- Population and age-sex rasters are modelled, not counted, and the age structure is uniform across the city.
- Scene counts vary from one to six a year, so year-to-year absolute temperatures reflect which days were clear. Only contrasts within a date are compared across years.

# Glossary

**LST.** Land surface temperature: how hot the ground, roof or canopy is, measured from orbit.
**Rural ring.** Land 1 to 10 km outside the study outline, used as the reference.
**Surface cool island.** A city whose surface is cooler than its surroundings.
**Composition class.** The anchor's twelve labels for the mix of built-up, bare, green and water cells inside one 30 m pixel.
**NDVI, NDBI, MNDWI, bare-soil index.** Spectral indices for greenness, built-up surface, water and moisture, and bare soil.
**UTFVI.** Urban thermal field variance index: each pixel's LST relative to the city mean. On the standard scale in kelvin, 1.7% of Kano is "strong" or worse (Bangalore reports 76% unfavourable); the index is relative to each city's own mean, so shares do not compare across cities.
**PT_k.** Walking time, in minutes at 5 km/h, to the five nearest clinics and five nearest schools, averaged.

# References

Ramachandra, T. V., Rana, R. S., Vinay, S. & Aithal, B. H. (2025). Urban heat island linkages with the landscape morphology. *Scientific Reports* 15, 24485. https://doi.org/10.1038/s41598-025-09141-5

Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. https://doi.org/10.5281/zenodo.7254221

U.S. Geological Survey. Landsat 8–9 Collection 2 Level-2 Science Products.

GRID3 (2025). Nigeria gridded population estimates v3.0 and age-sex structures.

Akpabio, W. (2026). *Fifteen minutes on foot: walking to clinics and schools in Lagos, Kano, Ibadan, Abuja and Port Harcourt.* https://whizialfa.github.io/15-min-cities-nigeria/
