"""OSM'den bina ayak izleri + isimli yerleri (POI) indirir -> data/osm_buildings.geojson, data/pois.geojson
Kullanım: python scripts/fetch_osm.py [--yenile]
"""
import json, sys, time, pathlib
import urllib.request, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from config import BBOX

W, S, E, N = BBOX
SERVERS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

def overpass(q, cache):
    """Ham yanıtı data/<cache> içine yazar; varsa tekrar indirmez (--yenile ile zorla)."""
    cf = DATA / cache
    if cf.exists() and "--yenile" not in sys.argv:
        print("   önbellekten:", cf.name)
        return json.loads(cf.read_text(encoding="utf-8"))
    last, wait = None, 5
    for attempt in range(6):   # sunucular yük altında 502/500 dönüyor -> üstel geri çekilme
        for s in SERVERS:
            try:
                print("->", s)
                req = urllib.request.Request(s, data=urllib.parse.urlencode({"data": q}).encode(),
                                             headers={"User-Agent": "odtu-3d-campus/0.1 (student project)"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    raw = r.read()
                data = json.loads(raw)
                cf.write_bytes(raw)
                return data
            except Exception as e:
                last = e; print("   başarısız:", e)
        print(f"   {wait} sn bekleniyor…"); time.sleep(wait); wait *= 2
    raise SystemExit(f"Hiçbir Overpass sunucusuna ulaşılamadı: {last}")

def ring(geom):
    pts = [(g["lon"], g["lat"]) for g in geom]
    if len(pts) >= 4 and pts[0] == pts[-1]:
        return pts
    return None

def to_features(elements):
    feats = []
    for el in elements:
        tags = el.get("tags", {})
        polys = []
        if el["type"] == "way" and el.get("geometry"):
            r = ring(el["geometry"])
            if r: polys.append([r])
        elif el["type"] == "relation":
            # basit: sadece kapalı 'outer' halkalar (iç avlular atlanır; bkz. README sınırlamalar)
            for m in el.get("members", []):
                if m.get("role") == "outer" and m.get("geometry"):
                    r = ring(m["geometry"])
                    if r: polys.append([r])
        for p in polys:
            feats.append({"type": "Feature",
                          "properties": {"osm_id": f'{el["type"]}/{el["id"]}', **tags},
                          "geometry": {"type": "Polygon", "coordinates": p}})
    return feats

bb = f"({S},{W},{N},{E})"
print("Binalar indiriliyor…")
b = overpass(f'[out:json][timeout:120];(way["building"]{bb};relation["building"]{bb};);out geom;', "raw_osm_buildings.json")
bf = to_features(b["elements"])
(DATA / "osm_buildings.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": bf}), encoding="utf-8")
named = sum(1 for f in bf if f["properties"].get("name"))
hts = sum(1 for f in bf if f["properties"].get("height") or f["properties"].get("building:levels"))
print(f"{len(bf)} bina, {named} isimli, {hts} tanesinde yükseklik/kat bilgisi var")

print("İsimli yerler (POI) indiriliyor…")
p = overpass(f'[out:json][timeout:120];(' +
             "".join(f'nwr["name"]["{k}"]{bb};' for k in ("amenity", "tourism", "leisure", "historic", "shop", "office")) +
             ');out center tags;', "raw_osm_pois.json")
pf, seen = [], set()
for el in p["elements"]:
    key = (el["type"], el["id"])
    if key in seen: continue
    seen.add(key)
    la = el.get("lat") or el.get("center", {}).get("lat"); lo = el.get("lon") or el.get("center", {}).get("lon")
    if la is None: continue
    pf.append({"type": "Feature", "properties": {"osm_id": f'{el["type"]}/{el["id"]}', **el.get("tags", {})},
               "geometry": {"type": "Point", "coordinates": [lo, la]}})
(DATA / "pois.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": pf}), encoding="utf-8")
print(f"{len(pf)} isimli POI kaydedildi")

# Yüzeyler: ham yanıtlar olduğu gibi saklanır, build_gltf.py viewer/surfaces.json'a çevirir
print("Yollar indiriliyor…")
r = overpass(f'[out:json][timeout:180];way["highway"]{bb};out geom;', "raw_osm_highways.json")
print(f'{len(r["elements"])} yol/yaya yolu')
print("Yeşil alan / su / otopark indiriliyor…")
AREA_FILTERS = ['["landuse"~"^(forest|grass|meadow|recreation_ground|village_green|orchard|cemetery)$"]',
                '["natural"~"^(wood|scrub|grassland|heath|water|wetland|bare_rock|sand)$"]',
                '["leisure"~"^(park|garden|pitch|track|golf_course|playground|stadium|swimming_pool)$"]',
                '["amenity"="parking"]', '["water"]']
r = overpass(f'[out:json][timeout:180];(' + "".join(f'way{f}{bb};relation{f}{bb};' for f in AREA_FILTERS) + ');out geom;',
             "raw_osm_areas.json")
print(f'{len(r["elements"])} alan')
print("Tekil ağaçlar / ağaç sıraları indiriliyor…")
r = overpass(f'[out:json][timeout:120];(node["natural"="tree"]{bb};way["natural"="tree_row"]{bb};);out geom;', "raw_osm_trees.json")
print(f'{len(r["elements"])} ağaç/ağaç sırası')
print("Kampüs sınırı indiriliyor…")
r = overpass(f'[out:json][timeout:120];(way["amenity"="university"]{bb};relation["amenity"="university"]{bb};);out geom;',
             "raw_osm_campus.json")
print(f'{len(r["elements"])} üniversite alanı')
