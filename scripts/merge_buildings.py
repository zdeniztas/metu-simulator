"""OSM (öncelikli) + Overture (boşluk doldurma) birleştirir -> data/buildings.geojson
Yükseklik önceliği:
  elle (height_overrides.json) > OSM height > OSM building:levels > Overture height > Overture num_floors
  > tahmin: aynı türdeki kampüs binalarının medyan katı > tür tablosu > taban alanı > varsayılan.
Ayrıca data/eksik_yukseklik.csv: gerçek yüksekliği olmayan OSM binaları, OSM'e girilecek öncelik sırasıyla.
"""
import csv, json, math, re, sys, pathlib, statistics
from collections import Counter, defaultdict
from shapely.geometry import shape, mapping
from shapely.strtree import STRtree
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import DEFAULT_HEIGHT, LEVEL_HEIGHT, LEVEL_HEIGHT_INST, ORIGIN
DATA = ROOT / "data"
M2 = 111320.0 * math.cos(math.radians(ORIGIN[0])) * 110540.0   # derece² -> m² (yaklaşık)

INST = {"university", "school", "college", "hospital", "public", "civic", "office", "government", "library",
        "education", "medical", "train_station", "transportation"}
# Kampüste yeterli örnek yoksa kullanılan tür tablosu: kat sayısı (veya ("h", metre) sabit yükseklik)
TYPE_LEVELS = {"house": 2, "detached": 2, "semidetached_house": 2, "apartments": 5, "residential": 4, "dormitory": 5,
               "school": 3, "education": 3, "university": 3, "college": 3, "office": 4, "commercial": 3, "retail": 2,
               "public": 3, "civic": 3, "government": 3, "hospital": 3, "medical": 3, "library": 3,
               "train_station": 1, "transportation": 1, "mosque": 1, "religious": 1, "industrial": 2,
               "garage": 1, "garages": 1, "shed": 1, "hut": 1, "kiosk": 1, "outbuilding": 1, "barn": 1,
               "agricultural": 1, "greenhouse": ("h", 4.0), "roof": ("h", 4.0), "carport": ("h", 3.0)}
MIN_SAMPLES = 3
UNI_NAME = re.compile(r"Bölüm|Fakülte|Enstitü|Blok|Amfi|Laboratuvar|Lab\b|Dekanl", re.I)

def num(v):
    if v is None: return None
    m = re.search(r"[\d.]+", str(v).replace(",", "."))
    try: return float(m.group()) if m else None
    except ValueError: return None

def load(p):
    f = DATA / p
    return json.loads(f.read_text(encoding="utf-8"))["features"] if f.exists() else []

lvl_h = lambda btype: LEVEL_HEIGHT_INST if btype in INST else LEVEL_HEIGHT

def rec(geom, name, btype, src, fid, height=None, levels=None, lsrc=None):
    """height: gerçek metre (varsa); levels: gerçek kat (varsa). Tahmin sonra yapılır."""
    b = {"geom": geom, "name": name, "btype": btype or "", "src": src, "id": fid, "levels": levels}
    if height is not None: b.update(h=height, h_src=f"{src}_height")
    elif levels is not None: b.update(h=levels * lvl_h(btype), h_src=lsrc)
    else: b.update(h=None, h_src=None)
    return b

osm = load("osm_buildings.geojson"); ovt = load("overture_buildings.geojson")
bl, geoms = [], []
for f in osm:
    t = f["properties"]
    g = shape(f["geometry"])
    if not g.is_valid: g = g.buffer(0)
    if g.is_empty: continue
    geoms.append(g)
    btype = t.get("building") if t.get("building") not in (None, "yes") else (t.get("amenity") or "")
    if not btype and UNI_NAME.search(t.get("name") or ""): btype = "university"   # building=yes bölüm binaları
    bl.append(rec(g, t.get("name") or t.get("name:en") or "", btype, "osm", t.get("osm_id", ""),
                  num(t.get("height")), num(t.get("building:levels")), "osm_levels"))
n_osm = len(bl)

if ovt:
    tree = STRtree(geoms) if geoms else None
    added = filled = 0
    for f in ovt:
        try: g = shape(f["geometry"])
        except Exception: continue
        if g.geom_type == "MultiPolygon": polys = list(g.geoms)
        elif g.geom_type == "Polygon": polys = [g]
        else: continue
        p = f["properties"]
        nm = p.get("names"); nm = (nm.get("primary") if isinstance(nm, dict) else "") or ""
        oh, ol = num(p.get("height")), num(p.get("num_floors"))
        for poly in polys:
            if poly.is_empty or poly.area == 0: continue
            if tree is not None:
                hits = [i for i in tree.query(poly) if geoms[i].intersection(poly).area > 0.3 * poly.area]
                if hits:
                    # çakışan OSM binasında gerçek yükseklik yoksa Overture'unkini aktar
                    for i in hits:
                        b = bl[i]
                        if b["h"] is None and (oh is not None or ol is not None):
                            b.update(rec(b["geom"], b["name"], b["btype"] or p.get("class") or p.get("subtype"), "overture",
                                         b["id"], oh, ol, "overture_floors") | {"src": "osm"}); filled += 1
                        elif not b["btype"] and (p.get("class") or p.get("subtype")):
                            b["btype"] = p.get("class") or p.get("subtype")
                    continue
            bl.append(rec(poly, nm, p.get("class") or p.get("subtype"), "overture", p.get("id", ""), oh, ol, "overture_floors"))
            added += 1
    print(f"Overture'dan {added} ek bina eklendi, {filled} OSM binasının yüksekliği Overture'dan dolduruldu")

# Elle düzeltmeler: [{"id": "way/123" | "name": "Tam Ad", "height": 18 | "levels": 4, "kaynak": "..."}]
ov_f = ROOT / "height_overrides.json"
overrides = json.loads(ov_f.read_text(encoding="utf-8")) if ov_f.exists() else []
used = set()
for b in bl:
    for k, o in enumerate(overrides):
        if (o.get("id") and o["id"] == b["id"]) or (o.get("name") and o["name"] == b["name"]):
            h = num(o.get("height")) if o.get("height") is not None else num(o.get("levels")) * lvl_h(b["btype"])
            b.update(h=h, h_src="manual"); used.add(k)
for k, o in enumerate(overrides):
    if k not in used: print("UYARI: height_overrides.json eşleşmedi:", o)

# Kampüsteki gerçek kat bilgisinden tür bazında medyan
samples = defaultdict(list)
for b in bl:
    if b["h_src"] in ("osm_levels", "overture_floors") and b["btype"]: samples[b["btype"]].append(b["levels"])
medians = {t: statistics.median(v) for t, v in samples.items() if len(v) >= MIN_SAMPLES}
print("Kampüs medyan kat (örnek sayısı):", {t: f"{m:g} ({len(samples[t])})" for t, m in medians.items()})

for b in bl:
    if b["h"] is not None: continue
    t, area = b["btype"], b["geom"].area * M2
    if t in medians: b.update(h=medians[t] * lvl_h(t), h_src="tahmin_tur_medyan")
    elif t in TYPE_LEVELS:
        v = TYPE_LEVELS[t]
        b.update(h=v[1] if isinstance(v, tuple) else v * lvl_h(t), h_src="tahmin_tur")
    elif area > 0:   # türü bilinmiyor: küçük yapılar kulübe/büfe, büyükler kampüs binası gibi
        lv = 1 if area < 60 else 2 if area < 300 else 3
        b.update(h=lv * LEVEL_HEIGHT, h_src="tahmin_alan")
    else: b.update(h=DEFAULT_HEIGHT, h_src="default")

out = [{"type": "Feature", "geometry": mapping(b["geom"]),
        "properties": {"name": b["name"], "height": round(b["h"], 1), "h_src": b["h_src"], "src": b["src"],
                       "id": b["id"], "type": b["btype"]}} for b in bl]
(DATA / "buildings.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": out}), encoding="utf-8")

# OSM'e girilecek öncelik listesi: isimliler önce, sonra büyük taban alanı
todo = [b for b in bl if b["src"] == "osm" and b["h_src"].startswith(("tahmin", "default"))]
todo.sort(key=lambda b: (not b["name"], -b["geom"].area))
with open(DATA / "eksik_yukseklik.csv", "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["osm", "isim", "tur", "taban_m2", "tahmini_yukseklik_m", "tahmin_yontemi", "lat", "lon"])
    for b in todo:
        c = b["geom"].centroid
        w.writerow([f"https://www.openstreetmap.org/{b['id']}", b["name"], b["btype"], round(b["geom"].area * M2),
                    round(b["h"], 1), b["h_src"], round(c.y, 6), round(c.x, 6)])

c = Counter(b["h_src"] for b in bl)
real = sum(v for k, v in c.items() if not k.startswith(("tahmin", "default")))
print(f"Toplam {len(bl)} bina (OSM {n_osm}). Yükseklik kaynakları:", dict(c))
print(f"Gerçek yüksekliği olan: {real} (%{100*real/max(1,len(bl)):.0f}); geri kalanı tahmin.")
print(f"{len(todo)} OSM binası data/eksik_yukseklik.csv'de (OSM'e girilecek öncelik sırası)")
