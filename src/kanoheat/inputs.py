"""Copy the Kano study frame from 15-min-cities-nigeria so both papers share one outline."""

from __future__ import annotations

import shutil

from .paths import DATA_PROCESSED, SIBLING

FILES = (
    "kano_study_boundary.gpkg",
    "kano_metro_lgas.gpkg",
    "kano_wards.gpkg",
    "kano_hexes.gpkg",
    "kano_places.gpkg",
    "kano_settlements.csv",
)


def sync(*, overwrite: bool = False) -> list[str]:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in FILES:
        src = SIBLING / name
        dst = DATA_PROCESSED / name
        if not src.exists():
            print(f"missing in sibling: {name}")
            continue
        if dst.exists() and not overwrite:
            continue
        shutil.copy2(src, dst)
        copied.append(name)
    return copied


if __name__ == "__main__":
    print("copied", sync())
