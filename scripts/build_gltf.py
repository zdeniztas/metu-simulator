"""buildings.geojson -> out/campus.glb (y-yukarı, x=doğu, z=-kuzey, metre) + viewer/landmarks.json
models/landmarks.json'daki elle modellenmiş yapılar (dosyası varsa) bloğun yerine geçer -> viewer/models.json
Kullanım: python scripts/build_gltf.py
"""
import json, math
import numpy as np, trimesh
from shapely.geometry import shape, Polygon, Point
from shapely.strtree import STRtree
from common import ROOT, proj, load_terrain, load_landmark_models
import surfaces, trees, facades, details

# Arazi (opsiyonel; scripts/fetch_dem.py). Yükseklikler orijindeki kota göre (orijin ~ y=0).
ground, ter = load_terrain()
(ROOT / "viewer").mkdir(exist_ok=True)
surf = extent = None
if ter:
    (ROOT / "viewer" / "terrain.json").write_text(json.dumps(ter), encoding="utf-8")
    print(f"Arazi {ter['nx']}x{ter['nz']} -> viewer/terrain.json (orijin kotu {ter['base']:.1f} m)")
    # Yollar ve yeşil alan/su: arazi dokusuna çizilir, bu yüzden arazi kapsamına kırpılır
    extent = (ter["x0"], ter["z0"], ter["x0"] + (ter["nx"] - 1) * ter["dx"], ter["z0"] + (ter["nz"] - 1) * ter["dz"])
    surf = surfaces.build(extent)
else:
    print("data/dem.npz yok -> düz zemin, yüzey dokusu yok (python scripts/fetch_dem.py)")

feats = json.loads((ROOT / "data" / "buildings.geojson").read_text(encoding="utf-8"))["features"]
pois_f = ROOT / "data" / "pois.geojson"
pois = json.loads(pois_f.read_text(encoding="utf-8"))["features"] if pois_f.exists() else []
# İsimsiz binaya içindeki POI'nin adını ver (bina adı etiketi için); otopark vb. alan POI'leri hariç
poi_pts = [(Point(*proj(*f["geometry"]["coordinates"])), f["properties"]["name"]) for f in pois
           if f["properties"].get("name") and f["properties"].get("amenity") not in ("parking", "bicycle_parking")]
poi_tree = STRtree([p for p, _ in poi_pts]) if poi_pts else None

# Elle modellenmiş önemli yapılar: dosyası olanların yerine geçtiği binalar blok olarak üretilmez
lms = load_landmark_models(feats)
replaced = set().union(*(m["replace"] for m in lms if m["has_model"])) if lms else set()
no_collide = set().union(*(m["replace"] for m in lms if m["has_model"] and not m["collision"])) if lms else set()
models = []
for m in lms:
    if not m["has_model"]: continue
    x, z = m["anchor_xz"]
    models.append({"key": m["key"], "file": "../models/" + m["file"].name, "x": round(x, 2), "z": round(z, 2),
                   "y": round(float(ground(x, z)), 2), "rot_deg": m["rot"], "scale": m["scale"]})
(ROOT / "viewer" / "models.json").write_text(json.dumps(models, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Önemli yapılar: {len(models)}/{len(lms)} modeli var -> viewer/models.json; {len(replaced)} bina bloğu yerine model")

campus = trees.campus_polygon()   # yerel (x, z); cephe stili seçimi için
parts = {s: ([], [], []) for s in facades.STYLES}   # stil -> (V, UV, F)
parts["roof"] = ([], [], []); parts["roof_tile"] = ([], [], [])
def add(key, V, UV, F):
    pv, pu, pf = parts.setdefault(key, ([], [], [])); k = len(pv); pv += V; pu += UV; pf += [(a + k, b + k, c + k) for a, b, c in F]
# Fotoğraflarda görülen detaylar (scripts/details.py): tribün, tepe pencereleri, camlı kuleler, çıkmalar, pilotis
det = details.Mesh(); det_count = {}
extra_tex = {}
gs = details.grandstand(surf, ground) if surf and not any(m["key"] == "devrim" and m["has_model"] for m in lms) else None   # elle model varsa o kullanılır
if gs: det, extra_tex["tribun"] = gs[0], gs[1]; det_count["tribün"] = 1
n_built, style_count, landmarks, footprints, skipped = 0, {}, [], [], 0
for f in feats:
    g = shape(f["geometry"])
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    for poly in polys:
        pp = Polygon([proj(x, y) for x, y in poly.exterior.coords])
        if not pp.is_valid: pp = pp.buffer(0)
        if pp.is_empty or pp.geom_type != "Polygon" or pp.area < 4: skipped += 1; continue
        # taban = ayak izi köşelerindeki en düşük zemin; yokuşta binanın üst tarafı toprağa gömülür
        ex, ey = np.array(pp.exterior.coords).T
        gz = ground(ex, -ey); base = float(gz.min())
        hgt = float(f["properties"]["height"]) + float(gz.max() - base)   # yokuş tarafında da tam yükseklik kalsın
        if f["properties"]["id"] not in replaced:   # elle modellenmişse blok yok; ayak izi (çarpışma) ve isim kalır
            c = pp.centroid
            st = facades.style_of(f["properties"], pp.area, campus is not None and campus.contains(Point(c.x, -c.y)))
            g = facades.gable(pp, base + hgt, st) if st in facades.PITCHED else None
            if g:   # beşik çatı + alın üçgenleri (duvar dokusuyla)
                add("roof_tile", *g[0]); add(st, *g[1])
            else:
                try:
                    add("roof", *facades.roof(pp, base + hgt))
                except Exception:
                    skipped += 1; continue
            dt = details.features(f["properties"], pp.area)
            wb = base   # pilotis: duvarlar zemin kat üstünden başlar, altta geri çekilmiş cam + kolonlar
            if dt.get("pilotis") and hgt > 2 * details.GF_M:
                nc = details.pilotis(det, pp, base)
                if nc is not None: wb = base + details.GF_M; det_count["kolon"] = det_count.get("kolon", 0) + nc
            add(st, *facades.walls(pp, wb, base + hgt - wb, st))
            if dt.get("tepe_pencere") and not g:
                det_count["tepe penceresi"] = det_count.get("tepe penceresi", 0) + details.skylights(det, pp, base + hgt, dt["tepe_pencere"])
            if dt.get("kule"):
                det_count["cam kule"] = det_count.get("cam kule", 0) + details.towers(det, pp, base, base + hgt, dt["kule"])
            if dt.get("cikma"):
                det_count["çıkma"] = det_count.get("çıkma", 0) + details.bays(det, pp, base + hgt)
            n_built += 1; style_count[st] = style_count.get(st, 0) + 1
        nm = f["properties"].get("name")
        label = nm
        if not label and poi_tree is not None:
            inside = [poi_pts[i][1] for i in poi_tree.query(pp, predicate="contains")]
            label = inside[0] if inside else ""
        # viewer çarpışması ve bina adı etiketi: t = çatı kotu (y), p = halka (x, z), n = ad
        if f["properties"]["id"] not in no_collide:
            footprints.append({"t": round(base + hgt, 1), "n": label or "",
                               "p": [[round(x, 2), round(-y, 2)] for x, y in pp.exterior.coords[:-1]]})
        if nm:
            c = pp.centroid
            landmarks.append({"name": nm, "kind": "building", "x": round(c.x, 1), "z": round(-c.y, 1),
                              "lat": round(poly.centroid.y, 6), "lon": round(poly.centroid.x, 6),
                              "height": f["properties"]["height"]})
if not n_built: raise SystemExit("Hiç bina üretilemedi")
for key, V, UV, F in det.items(): add(key, V, UV, F)
print(f"Detaylar (details.py): {det_count}")
# Stil başına bir mesh (kendi dokusuyla) + ortak çatı mesh'i. Duvar dörtgenleri köşe paylaşmaz -> düz gölgeleme.
scene, tris = trimesh.Scene(), 0
for key, (V, UV, F) in parts.items():
    if not F: continue
    if key in extra_tex: img = extra_tex[key]
    elif key in details.TEXTURES: img = details.TEXTURES[key]()
    else: img = facades.roof_texture("tile" if key == "roof_tile" else "flat") if key.startswith("roof") else facades.texture(key)
    m = trimesh.Trimesh(np.array(V), np.array(F), process=False)
    m.visual = trimesh.visual.TextureVisuals(uv=np.array(UV), material=facades.material(img, key))
    m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0]))  # z-yukarı -> y-yukarı
    scene.add_geometry(m, node_name=f"bina_{key}"); tris += len(F)
(ROOT / "out").mkdir(exist_ok=True)
scene.export(ROOT / "out" / "campus.glb", include_normals=True)   # normalsiz GLB three.js'te siyah görünüyor
print(f"{n_built} bina -> out/campus.glb ({tris} üçgen), stiller {style_count}, atlanan: {skipped}")
(ROOT / "viewer").mkdir(exist_ok=True)
(ROOT / "viewer" / "footprints.json").write_text(json.dumps(footprints, separators=(",", ":")), encoding="utf-8")
print(f"{len(footprints)} ayak izi -> viewer/footprints.json ({sum(1 for f in footprints if f['n'])} isimli)")
if surf: trees.build(extent, footprints, surf)

for f in pois:
    lo, la = f["geometry"]["coordinates"]; x, y = proj(lo, la)
    t = f["properties"]
    landmarks.append({"name": t.get("name", ""), "name_en": t.get("name:en", ""), "kind": "poi",
                      "x": round(x, 1), "z": round(-y, 1), "lat": round(la, 6), "lon": round(lo, 6), "height": 0})
(ROOT / "viewer").mkdir(exist_ok=True)
(ROOT / "viewer" / "landmarks.json").write_text(json.dumps(landmarks, ensure_ascii=False), encoding="utf-8")
print(f"{len(landmarks)} isimli yer -> viewer/landmarks.json")
