# Processed layers

`scene_inventory.csv` is every Landsat 8/9 Collection 2 Level-2 scene over the Kano outline since 2013, with the share of the outline each footprint covers (`coverage`) and, for candidates, the share of outline pixels clear in QA_PIXEL (`city_clear`). Usable scenes have both ≥ 0.98.

The Kano boundary, LGAs, wards, hexes, places and settlements are copied from `15-min-cities-nigeria` by `kanoheat.inputs`. Geopackages are gitignored.
