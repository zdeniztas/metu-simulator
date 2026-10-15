"""OSM yolları ve yeşil alan/su/otopark alanları -> viewer/surfaces.json (yerel x, z metre; arazi kapsamına kırpılmış)
build_gltf.py tarafından çağrılır. Viewer bunları arazi dokusuna çizer.
Biçim: {"extent": [x0, z0, x1, z1], "areas": [{"k": tür, "r": [halka, ...]}], "lines": [{"k": "road"|"path", "w": m, "p": [[x, z], ...]}]}
Alan halkaları evenodd ile doldurulur (ilk halka dış, kalanlar delik).
"""
import json
from shapely.geometry import LineString, Polygon, MultiPolygon, box
from shapely.ops import linemerge, polygonize, unary_union
from common import ROOT, proj

AREA_ORDER = ["forest", "scrub", "grass", "park", "pitch", "track", "parking", "paved", "bare", "water"]   # alttan üste
ROAD_W = {"motorway": 14, "trunk": 14, "primary": 12, "secondary": 10, "tertiary": 8, "unclassified": 6, "residential": 6,
          "living_street": 5, "service": 4, "road": 5, "track": 3}
PATH_W = {"pedestrian": 4, "footway": 2, "path": 2, "cycleway": 2, "bridleway": 2, "steps": 2}

def area_kind(t):
    if t.get("parking") in ("underground", "multi-storey", "rooftop"): return None
    if t.get("natural") in ("water", "wetland") or "water" in t or t.get("leisure") == "swimming_pool": return "water"
    if t.get("landuse") == "forest" or t.get("natural") == "wood": return "forest"
    if t.get("natural") in ("scrub", "heath"): return "scrub"
    if t.get("leisure") in ("park", "garden", "playground", "golf_course"): return "park"
    if t.get("landuse") in ("grass", "meadow", "recreation_ground", "village_green", "orchard", "cemetery") \
            or t.get("natural") == "grassland": return "grass"
    if t.get("leisure") == "pitch": return "pitch"
    if t.get("leisure") == "track": return "track"
    if t.get("amenity") == "parking": return "parking"
    if t.get("natural") in ("bare_rock", "sand"): return "bare"
    return None   # stadium vb.: kendisi çizilmez, içindeki saha/pist çizilir

def xz(geom): return [(proj(g["lon"], g["lat"])[0], -proj(g["lon"], g["lat"])[1]) for g in geom]

def rings_of(poly):
    return [[[round(x, 1), round(z, 1)] for x, z in r.coords] for r in [poly.exterior, *poly.interiors]]

def build(extent):
    clip = box(*extent)
    raw = lambda n: json.loads((ROOT / "data" / n).read_text(encoding="utf-8"))["elements"] if (ROOT / "data" / n).exists() else []
    areas = {k: [] for k in AREA_ORDER}
    for el in raw("raw_osm_areas.json"):
        k = area_kind(el.get("tags", {}))
        if not k: continue
        if el["type"] == "way":
            pts = xz(el.get("geometry", []))
            if len(pts) < 4 or pts[0] != pts[-1]: continue
            g = Polygon(pts)
        else:   # multipolygon: parçalı halkaları birleştir; dış - iç
            def poly_of(role):
                ls = [LineString(xz(m["geometry"])) for m in el.get("members", [])
                      if m.get("role") == role and m.get("type") == "way" and len(m.get("geometry", [])) >= 2]
                return unary_union(list(polygonize(linemerge(ls)))) if ls else Polygon()
            g = poly_of("outer").difference(poly_of("inner"))
        if not g.is_valid: g = g.buffer(0)
        g = g.intersection(clip)
        for p in (g.geoms if isinstance(g, MultiPolygon) else [g]):
            if isinstance(p, Polygon) and not p.is_empty and p.area > 1: areas[k].append(p)
    lines, n_road, n_path = [], 0, 0
    for el in raw("raw_osm_highways.json"):
        t = el.get("tags", {}); hw = t.get("highway", "").removesuffix("_link")
        if t.get("tunnel") in ("yes", "building_passage") or t.get("indoor") == "yes" or t.get("level", "0").startswith("-"): continue
        pts = xz(el.get("geometry", []))
        if len(pts) < 2: continue
        if t.get("area") == "yes" and pts[0] == pts[-1] and len(pts) >= 4:   # meydan/yaya alanı
            p = Polygon(pts).buffer(0).intersection(clip)
            for q in (p.geoms if isinstance(p, MultiPolygon) else [p]):
                if isinstance(q, Polygon) and not q.is_empty: areas["paved"].append(q)
            continue
        if hw in ROAD_W: k, w = "road", ROAD_W[hw]
        elif hw in PATH_W: k, w = "path", PATH_W[hw]
        else: continue
        if t.get("width"):
            try: w = float(t["width"].replace(",", ".").split()[0])
            except ValueError: pass
        g = LineString(pts).intersection(clip)
        for ln in (g.geoms if hasattr(g, "geoms") else [g]):
            if isinstance(ln, LineString) and not ln.is_empty:
                lines.append({"k": k, "w": w, "p": [[round(x, 1), round(z, 1)] for x, z in ln.coords]})
                if k == "road": n_road += 1
                else: n_path += 1
    lines.sort(key=lambda l: (l["k"] == "road", l["w"]))   # önce yaya yolları, sonra dar->geniş araç yolları
    out = {"extent": [round(v, 1) for v in extent],
           "areas": [{"k": k, "r": rings_of(p)} for k in AREA_ORDER for p in areas[k]], "lines": lines}
    (ROOT / "viewer" / "surfaces.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"Yüzeyler -> viewer/surfaces.json: {n_road} araç yolu, {n_path} yaya yolu, alanlar " +
          ", ".join(f"{k} {len(v)}" for k, v in areas.items() if v))
    return out
