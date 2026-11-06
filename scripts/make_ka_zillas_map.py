"""
Builds ai_app/app/static/ka_zillas.json, the zilla outlines of the dashboard's Karnataka map, from the Karnataka
Geographic Information System (KGIS, kgis.ksrsac.in) boundaries as republished under CC0 at github.com/samashti/KGIS
(data/output/District_Boundaries.gpkg.zip and Taluk_Boundaries.gpkg.zip).

KGIS districts still hold Ballari undivided, so Vijayanagara (formed 2021) and the new Ballari are drawn as the union of
their KGIS taluks; the other 29 zillas are the KGIS district outlines. Names are mapped to the warehouse's zilla
names, every outline is simplified to well under a pixel of the dashboard map and coordinates are rounded to 3 decimals.

usage:  python scripts/make_ka_zillas_map.py <District_Boundaries.gpkg> <Taluk_Boundaries.gpkg>
needs:  shapely (only this script; the app does not)
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

from shapely import wkb
from shapely.geometry import MultiPolygon, Polygon, mapping
from shapely.ops import unary_union

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "ai_app" / "app" / "static" / "ka_zillas.json"
TOLERANCE = 0.003          # degrees (~300 m); one pixel of the 640-px-high map is about 0.012 degrees
MIN_PART = 0.0002          # degrees squared (~2 km2): smaller islands and slivers are dropped

NAMES = {"Bengaluru (Rural)": "Bengaluru Rural", "Bengaluru (Urban)": "Bengaluru Urban",
         "Chamarajanagara": "Chamarajanagar", "Kalburgi": "Kalaburagi", "Kolara": "Kolar",
         "Ramanagara": "Bengaluru South (Ramanagara)"}
# KGIS taluk codes of undivided Ballari (12xx) and the zilla each belongs to now
BALLARI_SPLIT = {"Vijayanagara": {"1201", "1202", "1203", "1207", "1209", "1211"},   # Hadagali, H.B.Halli, Hosapete,
                 "Ballari": {"1204", "1205", "1206", "1208", "1210"}}                # Kudligi, Kotturu, Harapanahalli


def gpkg_geom(blob: bytes):
    """A GeoPackage geometry blob: 'GP', version, flags (envelope size in bits 1-3), srs id, envelope, then WKB."""
    flags = blob[3]
    env = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 7]
    return wkb.loads(blob[8 + env:])


def tidy(g) -> MultiPolygon | Polygon:
    g = g.buffer(0).simplify(TOLERANCE, preserve_topology=True)
    parts = [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if isinstance(p, Polygon) and p.area >= MIN_PART]
    parts = [Polygon(p.exterior) for p in parts]      # holes are slivers at this scale
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def rounded(geom: dict) -> dict:
    r = lambda ring: [[round(x, 3), round(y, 3)] for x, y in ring]
    if geom["type"] == "Polygon":
        return {"type": "Polygon", "coordinates": [r(ring) for ring in geom["coordinates"]]}
    return {"type": "MultiPolygon", "coordinates": [[r(ring) for ring in poly] for poly in geom["coordinates"]]}


def main(district_gpkg: str, taluk_gpkg: str) -> None:
    parts: dict[str, list] = {}
    with sqlite3.connect(f"file:{district_gpkg}?mode=ro", uri=True) as con:
        for name, blob in con.execute("SELECT KGISDist_1, geom FROM District_Boundaries"):
            if name != "Ballari":
                parts.setdefault(NAMES.get(name, name), []).append(gpkg_geom(blob))
    with sqlite3.connect(f"file:{taluk_gpkg}?mode=ro", uri=True) as con:
        for code, blob in con.execute("SELECT KGISTalukC, geom FROM Taluk_Boundaries WHERE KGISTalukC LIKE '12%'"):
            zilla = next(z for z, codes in BALLARI_SPLIT.items() if code in codes)
            parts.setdefault(zilla, []).append(gpkg_geom(blob))
    feats = [{"type": "Feature", "properties": {"name": z}, "geometry": rounded(mapping(tidy(unary_union(gs))))}
             for z, gs in sorted(parts.items())]
    if len(feats) != 31:
        sys.exit(f"expected 31 zillas, got {len(feats)}: {[f['properties']['name'] for f in feats]}")
    doc = {"type": "FeatureCollection",
           "_note": "Zilla outlines from the Karnataka Geographic Information System (KGIS, kgis.ksrsac.in; CC0 copy at "
                    "github.com/samashti/KGIS). Vijayanagara and Ballari are the unions of their KGIS taluks. Simplified "
                    "for display; not an authoritative boundary. Built by scripts/make_ka_zillas_map.py.",
           "features": feats}
    OUT.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(feats)} zillas, {OUT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
