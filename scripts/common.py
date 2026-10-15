"""build_gltf.py ve export_landmark_refs.py'nin ortak parçaları: projeksiyon, arazi, önemli yapı manifesti."""
import json, math, sys, time, pathlib, urllib.request, urllib.parse
import numpy as np
from shapely.geometry import shape, Point, Polygon
from shapely.ops import unary_union
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import ORIGIN
LAT0, LON0 = ORIGIN
KX = 111320.0 * math.cos(math.radians(LAT0)); KY = 110540.0
def proj(lon, lat): return ((lon - LON0) * KX, (lat - LAT0) * KY)   # (doğu, kuzey) metre

def load_terrain():
    """-> (ground(x, z) [orijin kotuna göre m], terrain dict | None). x = doğu, z = -kuzey.
    Izgara yerel koordinatta düzenlidir: x = x0 + i*dx, z = z0 + j*dz (viewer'daki bilinear ile aynı)."""
    dem_f = ROOT / "data" / "dem.npz"
    if not dem_f.exists():
        return (lambda x, z: np.zeros(np.shape(x))), None
    d = np.load(dem_f)
    H = d["h"]
    x0, n0 = proj(float(d["lon0"]), float(d["lat0"])); z0 = -n0
    dx, dz = float(d["dlon"]) * KX, -float(d["dlat"]) * KY
    def ground_raw(x, z):   # bilinear; ızgara dışında kenara kenetlenir
        fi = np.clip((np.asarray(x) - x0) / dx, 0, H.shape[1] - 1.001); fj = np.clip((np.asarray(z) - z0) / dz, 0, H.shape[0] - 1.001)
        i, j = fi.astype(int), fj.astype(int); u, v = fi - i, fj - j
        return (H[j, i] * (1 - u) * (1 - v) + H[j, i + 1] * u * (1 - v) + H[j + 1, i] * (1 - u) * v + H[j + 1, i + 1] * u * v)
    base = float(ground_raw(0.0, 0.0))
    ter = {"nx": H.shape[1], "nz": H.shape[0], "x0": round(x0, 2), "z0": round(z0, 2), "dx": round(dx, 4), "dz": round(dz, 4),
           "base": round(base, 2), "h": [round(float(v) - base, 2) for v in H.ravel()]}
    return (lambda x, z: ground_raw(x, z) - base), ter

def _overpass_geoms(ids):
    """OSM nesnelerinin geometrisini çeker (data/raw_landmarks.json önbelleği). ids: ["way/1", "node/2", ...]"""
    cf = ROOT / "data" / "raw_landmarks.json"
    cache = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    need = [i for i in ids if i not in cache]
    if need:
        q = "[out:json][timeout:60];(" + "".join(f"{t}({n});" for t, n in (i.split("/") for i in need)) + ");out geom;"
        wait = 5
        for attempt in range(6):
            try:
                req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                             data=urllib.parse.urlencode({"data": q}).encode(),
                                             headers={"User-Agent": "odtu-3d-campus/0.1 (student project)"})
                with urllib.request.urlopen(req, timeout=120) as r: els = json.load(r)["elements"]
                break
            except Exception as e:
                print("   Overpass başarısız:", e, f"- {wait} sn"); time.sleep(wait); wait *= 2
        else:
            raise SystemExit("Önemli yapı geometrisi indirilemedi")
        for el in els:
            k = f'{el["type"]}/{el["id"]}'
            if el["type"] == "node": cache[k] = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
            elif el["type"] == "way":
                cache[k] = {"type": "Polygon", "coordinates": [[[g["lon"], g["lat"]] for g in el["geometry"]]]}
            else:   # relation: dış halkalar
                rings = [[[g["lon"], g["lat"]] for g in m["geometry"]] for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
                cache[k] = {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}
        cf.write_text(json.dumps(cache), encoding="utf-8")
    return {i: cache[i] for i in ids if i in cache}

def load_landmark_models(features):
    """models/landmarks.json'u çözer. features: buildings.geojson özellikleri (anchor geometri kaynağı).
    -> [{key, name, file (Path), has_model, anchor_ll (lon, lat), anchor_xz, outline_ll (shapely, lon/lat), replace (set), rot, scale}]"""
    mf = ROOT / "models" / "landmarks.json"
    if not mf.exists(): return []
    entries = json.loads(mf.read_text(encoding="utf-8"))
    by_id = {}
    for f in features: by_id.setdefault(f["properties"]["id"], []).append(shape(f["geometry"]))
    missing = [e["anchor"] for e in entries if e["anchor"] not in by_id]
    fetched = _overpass_geoms(missing) if missing else {}
    out = []
    for e in entries:
        a = e["anchor"]
        g = unary_union(by_id[a]) if a in by_id else shape(fetched[a]) if a in fetched else None
        if g is None: print("UYARI: anchor bulunamadı:", e["key"], a); continue
        c = g.centroid if g.geom_type != "Point" else g
        replace = set(e.get("replace", []))
        if e.get("replace_inside") and g.geom_type != "Point":   # alanın içindeki tüm binalar (ör. stadyum tribünleri)
            replace |= {f["properties"]["id"] for f in features if g.contains(shape(f["geometry"]).centroid)}
        fpath = ROOT / "models" / e["file"]
        out.append({"key": e["key"], "name": e.get("name", e["key"]), "file": fpath, "has_model": fpath.exists(),
                    "anchor_ll": (c.x, c.y), "anchor_xz": (proj(c.x, c.y)[0], -proj(c.x, c.y)[1]),
                    "outline_ll": g if g.geom_type != "Point" else None, "replace": replace,
                    "rot": float(e.get("rot_deg", 0)), "scale": float(e.get("scale", 1)),
                    "collision": bool(e.get("collision", True))})
    return out
