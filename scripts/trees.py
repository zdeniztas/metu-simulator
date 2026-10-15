"""Ağaç konumları -> viewer/trees.json  (build_gltf.py çağırır)
Kaynak: ESA WorldCover 2021 sınıf 10 (ağaç örtüsü, 10 m; scripts/fetch_landcover.py) + OSM natural=tree / tree_row.
Her ağaç pikseline bir ağaç (piksel içinde rastgele kaydırılmış); bina ayak izine ve yola düşenler elenir.
ODTÜ sınırı içinde ek olarak kısmi tamamlama yapılır (bkz. build içindeki not).
Biçim: {"d": [x, z, ölçek, tür, ...]}  tür 0 = yapraklı, 1 = iğne yapraklı (çam). y viewer'da araziden alınır.
"""
import json
import numpy as np, shapely
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union, polygonize, linemerge
from common import ROOT, proj, KX, KY

CAMPUS_NAME = "Orta Doğu Teknik Üniversitesi"

def campus_polygon():
    """OSM amenity=university içinden ODTÜ sınırı (yerel x, z); yoksa None"""
    f = ROOT / "data" / "raw_osm_campus.json"
    if not f.exists(): return None
    for el in json.loads(f.read_text(encoding="utf-8"))["elements"]:
        if el.get("tags", {}).get("name") != CAMPUS_NAME: continue
        xz = lambda geom: [(proj(g["lon"], g["lat"])[0], -proj(g["lon"], g["lat"])[1]) for g in geom]
        if el["type"] == "way": return Polygon(xz(el["geometry"])).buffer(0)
        ls = [LineString(xz(m["geometry"])) for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
        return unary_union(list(polygonize(linemerge(ls))))
    return None

def build(extent, footprints, surf):
    rng = np.random.default_rng(42)   # her derlemede aynı orman
    pts = []   # (x, z, tür olasılığı için orman mı)
    wc_f = ROOT / "data" / "worldcover.npz"
    if wc_f.exists():
        d = np.load(wc_f); C = d["c"]
        jj, ii = np.nonzero(C == 10)
        lon = float(d["lon0"]) + ii * float(d["dlon"]); lat = float(d["lat0"]) + jj * float(d["dlat"])
        x, n = proj(lon, lat); z = -n
        px, pz = abs(float(d["dlon"])) * KX, abs(float(d["dlat"])) * KY   # piksel boyu (m)
        x = x + rng.uniform(-0.45, 0.45, x.size) * px; z = z + rng.uniform(-0.45, 0.45, z.size) * pz
        pts.append(np.column_stack([x, z, np.zeros(x.size)]))
        # Kampüs içi tamamlama (yaklaşım): 10 m'lik pikselde binaya yakın ağaçlar "yapılaşmış" (50) sayılıyor, oysa
        # ODTÜ çekirdeği ağaçlık. Kampüs sınırı içinde 50'ye %35, çayıra (30) %10 olasılıkla ağaç; engeller yine elenir.
        campus = campus_polygon()
        if campus is not None:
            jj, ii = np.nonzero((C == 50) | (C == 30))
            p = np.where(C[jj, ii] == 50, 0.35, 0.10); sel = rng.random(p.size) < p; jj, ii = jj[sel], ii[sel]
            lon = float(d["lon0"]) + ii * float(d["dlon"]); lat = float(d["lat0"]) + jj * float(d["dlat"])
            x, n = proj(lon, lat); z = -n
            x = x + rng.uniform(-0.45, 0.45, x.size) * px; z = z + rng.uniform(-0.45, 0.45, z.size) * pz
            shapely.prepare(campus); inside = shapely.contains_xy(campus, x, z)
            pts.append(np.column_stack([x[inside], z[inside], np.zeros(int(inside.sum()))]))
            print(f"   kampüs içi tamamlama: +{int(inside.sum())} ağaç adayı")
    osm_n = 0
    tf = ROOT / "data" / "raw_osm_trees.json"
    if tf.exists():
        for el in json.loads(tf.read_text(encoding="utf-8"))["elements"]:
            if el["type"] == "node":
                x, n = proj(el["lon"], el["lat"]); pts.append(np.array([[x, -n, 1]])); osm_n += 1
            elif el.get("geometry"):   # ağaç sırası: 8 m arayla
                ln = LineString([(proj(g["lon"], g["lat"])[0], -proj(g["lon"], g["lat"])[1]) for g in el["geometry"]])
                for s in np.arange(0, ln.length, 8.0):
                    p = ln.interpolate(s); pts.append(np.array([[p.x, p.y, 1]])); osm_n += 1
    if not pts:
        print("Ağaç verisi yok (python scripts/fetch_landcover.py)"); return
    P = np.vstack(pts)
    # Engeller: bina ayak izleri (+1,5 m) ve yollar (genişlik/2 + 1 m); OSM ağaçları (sütun 2 = 1) elenmez
    obst = [Polygon(f["p"]).buffer(1.5) for f in footprints if len(f["p"]) >= 3]
    obst += [LineString(l["p"]).buffer(l["w"] / 2 + 1.0) for l in surf["lines"] if len(l["p"]) >= 2]
    obst += [Polygon(a["r"][0]).buffer(0) for a in surf["areas"] if a["k"] in ("water", "parking", "pitch", "track", "paved")]
    O = unary_union(obst); shapely.prepare(O)
    inside_ext = (P[:, 0] > extent[0]) & (P[:, 0] < extent[2]) & (P[:, 1] > extent[1]) & (P[:, 1] < extent[3])
    keep = inside_ext & ((P[:, 2] == 1) | ~shapely.contains_xy(O, P[:, 0], P[:, 1]))
    P = P[keep]
    forest = unary_union([Polygon(a["r"][0]).buffer(0) for a in surf["areas"] if a["k"] == "forest"]); shapely.prepare(forest)
    in_forest = shapely.contains_xy(forest, P[:, 0], P[:, 1])
    kind = (rng.random(len(P)) < np.where(in_forest, 0.8, 0.4)).astype(int)   # ormanda çoğunluk çam
    scale = rng.uniform(0.75, 1.3, len(P))
    D = np.column_stack([P[:, 0].round(1), P[:, 1].round(1), scale.round(2), kind]).ravel().tolist()
    (ROOT / "viewer" / "trees.json").write_text(json.dumps({"d": D}, separators=(",", ":")), encoding="utf-8")
    print(f"{len(P)} ağaç -> viewer/trees.json (OSM {osm_n} tekil, {int(in_forest.sum())} orman içinde, %{100*kind.mean():.0f} çam)")
