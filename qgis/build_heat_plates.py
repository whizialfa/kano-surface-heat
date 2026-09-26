"""A3 plates for Kano surface heat. Run with QGIS's Python.

The furniture (neatline, title, legend packing, footnote, north, scale, credit,
furniture-aware framing) is the walking paper's `_kigali_layout`, imported from
15-min-cities-nigeria so both papers print as one family.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PROCESSED = HERE / "data" / "processed"
sys.path.insert(0, str(HERE.parent / "15-min-cities-nigeria" / "qgis"))

import build_city_project as bcp  # noqa: E402
from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsFillSymbol,
    QgsLayoutSize,
    QgsLegendRenderer,
    QgsProject,
    QgsRasterLayer,
)

_pin_legend_rows = bcp._pin_legend


def _pin_legend_snug(legend, layer, **kwargs):
    """Row-count sizing leaves air under short legends; shrink to the rendered content."""
    w, h = _pin_legend_rows(legend, layer, **kwargs)
    content = QgsLegendRenderer(legend.model(), legend.legendSettings()).minimumSize()
    snug = float(content.height()) + 0.6
    if 20.0 < snug < h:
        legend.attemptResize(QgsLayoutSize(w, snug, bcp.MM))
        print(f"    legend snug {w:.1f}×{snug:.1f} mm", flush=True)
        return w, snug
    return w, h


bcp._pin_legend = _pin_legend_snug

SLUG = "kano"
FILL_ALPHA = 204

# ColorBrewer RdYlBu, reversed: blue is cooler ground, red is hotter.
HEAT_BREAKS = [
    (0.0, 44.0, f"69,117,180,{FILL_ALPHA}", "≤ 44"),
    (44.0, 45.0, f"145,191,219,{FILL_ALPHA}", "44–45"),
    (45.0, 46.0, f"204,226,238,{FILL_ALPHA}", "45–46"),
    (46.0, 47.0, f"254,224,144,{FILL_ALPHA}", "46–47"),
    (47.0, 48.0, f"252,141,89,{FILL_ALPHA}", "47–48"),
    (48.0, 60.0, f"215,48,39,{FILL_ALPHA}", "> 48"),
]

# Codes from kanoheat.exposure.HEAT_WALK.
HEAT_WALK_BREAKS = [
    (0.5, 1.5, "165,15,21,225", "Hot and far"),
    (1.5, 2.5, "251,106,74,215", "Hot, near"),
    (2.5, 3.5, "66,146,198,205", "Cooler, far"),
    (3.5, 4.5, "198,219,239,205", "Cooler, near"),
    (4.5, 5.5, "190,186,180,110", "Few people"),
]


# Codes from kanoheat.lulc.CLASSES.
LULC_BREAKS = [
    (0.5, 1.5, f"158,76,66,{FILL_ALPHA}", "Built-up"),
    (1.5, 2.5, f"236,205,120,{FILL_ALPHA}", "Cropland"),
    (2.5, 3.5, f"205,190,172,{FILL_ALPHA}", "Bare ground"),
    (3.5, 4.5, f"186,206,122,{FILL_ALPHA}", "Grass"),
    (4.5, 5.5, f"138,158,84,{FILL_ALPHA}", "Shrubs"),
    (5.5, 6.5, f"38,110,56,{FILL_ALPHA}", "Trees"),
    (6.5, 7.5, f"58,124,196,{FILL_ALPHA}", "Water and wetland"),
]


def _layers():
    osm = QgsRasterLayer(
        "type=xyz&url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&crs=EPSG3857",
        "OpenStreetMap",
        "wms",
    )
    boundary = bcp._vector(PROCESSED / "kano_study_boundary.gpkg", "kano_study_boundary", "1 Study boundary")
    boundary.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "0,0,0,0", "outline_color": "28,25,22,255", "outline_width": "0.9", "outline_width_unit": "MM",
    }))
    wards = bcp._vector(PROCESSED / "kano_wards.gpkg", "kano_wards", "2 Wards (GRID3 operational)")
    wards.setLabelsEnabled(False)
    wards.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "0,0,0,0", "outline_color": "90,84,78,165", "outline_width": "0.22", "outline_width_unit": "MM",
    }))
    places = bcp._vector(PROCESSED / "kano_places.gpkg", "kano_places", "2b Named places (OSM)")
    places.renderer().setSymbol(bcp._marker("circle", "0,0,0,0", "0.1", outline="0,0,0,0"))
    bcp._place_labels(places, SLUG)

    heat = bcp._vector(PROCESSED / "kano_hex_heat.gpkg", "kano_hex_heat", "3 Hot-season surface temperature")
    bcp._graduated(heat, "lst", HEAT_BREAKS)
    heat_walk = bcp._vector(PROCESSED / "kano_hex_heat.gpkg", "kano_hex_heat", "4 Heat and walking time")
    bcp._graduated(heat_walk, "heat_walk", HEAT_WALK_BREAKS)
    lulc = bcp._vector(PROCESSED / "kano_lulc_30m.gpkg", "kano_lulc_30m", "5 Land cover (WorldCover 2021, 30 m)")
    bcp._graduated(lulc, "code", LULC_BREAKS, outline_width="0")
    return osm, boundary, wards, places, heat, heat_walk, lulc


def main() -> None:
    QgsApplication.setPrefixPath(os.environ["QGIS_PREFIX_PATH"], True)
    app = QgsApplication([], False)
    app.initQgis()
    bcp.MAPS = HERE / "maps"

    out = HERE / "qgis" / "kano_heat.qgz"
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
    project.setPresetHomePath(str(HERE))
    project.setFileName(str(out))

    osm, boundary, wards, places, heat, heat_walk, lulc = _layers()
    for layer in (osm, lulc, heat, heat_walk, wards, places, boundary):
        project.addMapLayer(layer, True)
    for hidden in (heat_walk, lulc):
        node = project.layerTreeRoot().findLayer(hidden.id())
        if node:
            node.setItemVisibilityChecked(False)

    overlays = [boundary, places, wards]
    heat.updateExtents()
    png = bcp._kigali_layout(
        project,
        SLUG,
        layout_name="Hot-season surface temperature",
        choropleth=heat,
        overlays=overlays,
        osm=osm,
        extent_wgs=heat.extent(),
        title="HOT GROUND IN KANO",
        subtitle="Surface temperature, March to May",
        caption=(
            "This map shows how hot the ground gets in the hot season, not the air. "
            "Each cell is a 200-metre neighbourhood, over twelve years of Landsat. "
            "Blue is cooler ground, red is hotter."
        ),
        legend_title="Surface heat, °C",
        export_stem="heat_plate",
    )
    print(f"  → {png.name}", flush=True)

    png = bcp._kigali_layout(
        project,
        SLUG,
        layout_name="Heat and walking time",
        choropleth=heat_walk,
        overlays=overlays,
        osm=osm,
        extent_wgs=heat.extent(),
        title="HOT GROUND AND LONG WALKS",
        subtitle="Kano, where both meet",
        caption=(
            "Hot is the hottest fifth of neighbourhoods where people live. "
            "Far is more than a 15-minute walk to five clinics and five schools. "
            "Dark red is hot and far: 261,000 people, 42,000 of them under five."
        ),
        legend_title="Heat and walk",
        export_stem="heat_walk_plate",
    )
    print(f"  → {png.name}", flush=True)

    png = bcp._kigali_layout(
        project,
        SLUG,
        layout_name="Land cover",
        choropleth=lulc,
        overlays=overlays,
        osm=osm,
        extent_wgs=heat.extent(),
        title="LAND COVER IN KANO",
        subtitle="What covers the ground",
        caption=(
            "This map shows what covers the ground, from ESA WorldCover 2021. "
            "Each cell is 30 metres, the most common cover among nine 10-metre cells. "
            "Built-up is 45% of the area and cropland 40%, bare earth in the hot season."
        ),
        legend_title="Land cover",
        export_stem="lulc_plate",
    )
    print(f"  → {png.name}", flush=True)

    ok = project.write(str(out))
    print(f"  project {'written' if ok else 'NOT written'}: {out.name}", flush=True)
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    main()
