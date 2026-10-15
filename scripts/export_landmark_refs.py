"""models/landmarks.json'daki her önemli yapı için Blender referans paketi -> models/ref/<key>_ref.glb + <key>_ref.json
Koordinatlar yapıya göre yereldir: orijin = anchor merkezi, yükseklik 0 = anchor'daki zemin.
glTF Y-yukarı; Blender'a (+Y Up varsayılanıyla) aktarınca: +X doğu, +Y kuzey, +Z yukarı, metre.
Nesneler: HEDEF_* (yerine model gelecek binalar, şu anki blok yüksekliğiyle), ALAN_SINIRI (bina olmayan anchor'ın OSM
sınırı), KOMSU_BINALAR, ARAZI (Copernicus GLO-30, 5 m örnekleme), KUZEY (kuzeyi gösteren 20 m'lik ok).
Kullanım: python scripts/export_landmark_refs.py   (önce merge_buildings.py; arazi için fetch_dem.py)
"""
import json, math
import numpy as np, trimesh
from shapely.geometry import shape, Polygon
from common import ROOT, proj, load_terrain, load_landmark_models

RADIUS = 200.0   # m; çevre binalar ve arazi parçası
STEP = 5.0       # m; arazi örnekleme aralığı

def mat(rgba, name):
    return trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
        name=name, baseColorFactor=rgba, metallicFactor=0.0, roughnessFactor=0.9))

def zup_to_yup(m):   # (doğu, kuzey, yukarı) -> glTF (x, y=yukarı, z=-kuzey)
    m.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [1, 0, 0])); return m

ground, ter = load_terrain()
BASE = ter["base"] if ter else 0.0   # orijin kotu (m, deniz seviyesinden)
feats = json.loads((ROOT / "data" / "buildings.geojson").read_text(encoding="utf-8"))["features"]
lms = load_landmark_models(feats)
outdir = ROOT / "models" / "ref"; outdir.mkdir(parents=True, exist_ok=True)

for lm in lms:
    ax, az = lm["anchor_xz"]; ae, an = ax, -az          # anchor (doğu, kuzey)
    g0 = float(ground(ax, az))
    loc = lambda lon, lat: (proj(lon, lat)[0] - ae, proj(lon, lat)[1] - an)   # anchor'a göre (doğu, kuzey)
    scene = trimesh.Scene()
    targets, neigh = [], []
    for f in feats:
        g = shape(f["geometry"]); p = f["properties"]
        polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
        for poly in polys:
            pp = Polygon([loc(x, y) for x, y in poly.exterior.coords])
            if not pp.is_valid: pp = pp.buffer(0)
            if pp.is_empty or pp.geom_type != "Polygon" or pp.area < 4: continue
            is_t = p["id"] in lm["replace"]
            if not is_t and math.hypot(pp.centroid.x, pp.centroid.y) > RADIUS: continue
            ex, ey = np.array(pp.exterior.coords).T
            gz = ground(ex + ae, -(ey + an)) - g0; base = float(gz.min())
            m = trimesh.creation.extrude_polygon(pp, float(p["height"]) + float(gz.max() - base))
            m.apply_translation([0, 0, base])
            (targets if is_t else neigh).append((m, p, pp))
    for k, (m, p, _) in enumerate(targets):
        m.visual = mat([1.0, 0.55, 0.1, 1.0], "hedef")
        scene.add_geometry(zup_to_yup(m), node_name=f"HEDEF_{k}_{p['id'].replace('/', '_')}")
    if neigh:
        m = trimesh.util.concatenate([t[0] for t in neigh]); m.visual = mat([0.75, 0.75, 0.75, 1.0], "komsu")
        scene.add_geometry(zup_to_yup(m), node_name="KOMSU_BINALAR")
    outline = None
    if lm["outline_ll"] is not None and not targets:   # bina olmayan alan (ör. stadyum): sınırı 0,5 m'lik şerit
        og = lm["outline_ll"]; opolys = list(og.geoms) if og.geom_type == "MultiPolygon" else [og]
        outline = [Polygon([loc(x, y) for x, y in op.exterior.coords]) for op in opolys]
        rings = [o.exterior.buffer(0.3) for o in outline]
        parts = []
        for r in rings:
            for rp in (list(r.geoms) if r.geom_type == "MultiPolygon" else [r]):
                parts.append(trimesh.creation.extrude_polygon(rp, 0.5))
        m = trimesh.util.concatenate(parts); m.visual = mat([1.0, 0.9, 0.0, 1.0], "sinir")
        scene.add_geometry(zup_to_yup(m), node_name="ALAN_SINIRI")
    # Arazi parçası: RADIUS karesinde STEP aralıklı ızgara
    n = int(2 * RADIUS / STEP) + 1
    xs = np.linspace(-RADIUS, RADIUS, n)
    E, N = np.meshgrid(xs, xs)
    Z = ground(E + ae, -(N + an)) - g0
    verts = np.column_stack([E.ravel(), N.ravel(), Z.ravel()])
    idx = np.arange(n * n).reshape(n, n)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    faces = np.vstack([np.column_stack([a, b, d]), np.column_stack([a, d, c])])   # yukarı bakan normaller
    m = trimesh.Trimesh(verts, faces, process=False); m.visual = mat([0.45, 0.62, 0.38, 1.0], "arazi")
    scene.add_geometry(zup_to_yup(m), node_name="ARAZI")
    arrow = trimesh.creation.box([1.0, 20.0, 0.3]); arrow.apply_translation([0, 10, 0.15])   # +kuzey yönünde
    arrow.visual = mat([0.85, 0.1, 0.1, 1.0], "kuzey")
    scene.add_geometry(zup_to_yup(arrow), node_name="KUZEY")
    scene.export(outdir / f"{lm['key']}_ref.glb")

    info = {"key": lm["key"], "name": lm["name"], "hedef_dosya": f"models/{lm['file'].name}", "model_var": lm["has_model"],
            "anchor": {"lat": round(lm["anchor_ll"][1], 7), "lon": round(lm["anchor_ll"][0], 7),
                       "zemin_kotu_m": round(g0 + BASE, 1) if ter else None},
            "eksenler": "Blender: +X doğu, +Y kuzey, +Z yukarı, metre; orijin = anchor merkezi, z=0 = anchor'daki zemin",
            "hedef_binalar": [{"id": p["id"], "isim": p["name"], "su_anki_yukseklik_m": p["height"], "yukseklik_kaynagi": p["h_src"],
                               "taban_m2": round(pp.area), "ayak_izi_dogu_kuzey_m": [[round(x, 2), round(y, 2)] for x, y in pp.exterior.coords]}
                              for _, p, pp in targets],
            "alan_siniri_dogu_kuzey_m": [[[round(x, 2), round(y, 2)] for x, y in o.exterior.coords] for o in outline] if outline else None,
            "arazi_yerel_min_max_m": [round(float(Z.min()), 1), round(float(Z.max()), 1)]}
    (outdir / f"{lm['key']}_ref.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{lm['key']}: {len(targets)} hedef bina, {len(neigh)} komşu, arazi {Z.min():+.1f}..{Z.max():+.1f} m"
          f"{', alan sınırı' if outline else ''} -> models/ref/{lm['key']}_ref.glb")
