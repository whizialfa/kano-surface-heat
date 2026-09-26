# Kano surface heat

Where the ground gets hottest in metropolitan Kano in the hot season, what covers it, and who lives on it.

Adaptation of Ramachandra, Rana, Vinay & Aithal (2025), [Urban heat island linkages with the landscape morphology](https://doi.org/10.1038/s41598-025-09141-5), *Scientific Reports* 15, 24485. **This is not a replication.** The anchor uses one April 2022 scene over humid Bangalore, uncorrected Landsat thermal, a field-trained land-use map, and no population. Here: medians of every clear Landsat 8/9 scene per season over semi-arid Kano, USGS Level-2 surface temperature, ESA WorldCover, and GRID3 population by age and sex on the same hexes as [`15-min-cities-nigeria`](https://github.com/whizialfa/15-min-cities-nigeria).

The full trace from raw input to each quoted number, and every place the method departs from the anchor, is in [`notes/metric_trace.md`](notes/metric_trace.md).

## Frame

- **Study area:** Kano metropolitan area, eight LGAs, 573 km², the same outline as the walking paper. A 1–10 km rural ring is the reference for surface heat-island intensity.
- **Headline season:** hot dry season, March–May. Harmattan (Nov–Feb) and wet (Jun–Sep) are comparisons.
- **Surface temperature:** Landsat Collection 2 Level-2 `ST_B10`, per-pixel median of scenes with ≥ 98% of the outline clear in QA_PIXEL. One footprint (WRS-2 188/052) covers the whole city.
- **Caveat on every map:** this is how hot the ground is, not the air people breathe.

## Status

| Stage | State |
|---|---|
| Scene inventory | 1,160 scenes searched, **142 clear over the city** (hot season 40, 2015–2026) |
| Hot-season LST 2026 | built, 6 scenes |
| Land-use composition (C1–C12) | next |
| Spectral indices and regressions | next |
| Population exposure | next |

First look, hot season 2026 (preliminary, one year): the rural ring's median surface is **45.0 °C** against **43.5 °C** inside the city. By day in the hot season Kano is a surface cool island. Inside the outline, Ungogo on the fringe is hottest (44.3 °C mean) and the old city coolest (Kano Municipal and Gwale 42.6 °C).

## Run

```bash
export PYTHONPATH="$PWD/src"
/opt/anaconda3/bin/python3.12 -m kanoheat.inputs          # copy the Kano frame from 15-min-cities-nigeria
/opt/anaconda3/bin/python3.12 -m kanoheat.scenes          # score every scene on the city (≈3 min)
/opt/anaconda3/bin/python3.12 -m kanoheat.lst --season hot --years 2015-2026
```

Rasters land in `data/raw/lst/` and are not committed. Times are logged in [`notes/task_times.md`](notes/task_times.md).
