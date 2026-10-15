"""Bina cephe görünümleri: prosedürel dokular + UV'li duvar/çatı mesh'i (build_gltf.py kullanır).
Görünümler kampüs fotoğraflarına BAKILARAK tanımlandı (Wikimedia Commons, SALT Research; kaynaklar building_looks.json'da).
Hiçbir fotoğraf kopyalanmaz ya da dokuya dönüştürülmez (SALT görselleri CC BY-NC-ND); dokular numpy ile çizilir.
Bir doku karesi = bir aks (bay_m) x bir kat (floor_m). Hangi binanın hangi görünümü alacağı: building_looks.json
kuralları (ilk eşleşen), yoksa aşağıdaki varsayılanlar (TAHMİN).
"""
import json, re
import numpy as np, trimesh
from PIL import Image
from shapely.geometry.polygon import orient
from common import ROOT

PX = 256   # doku karesi kenarı (piksel)
STYLES = {   # bay_m: pencere aksı genişliği, floor_m: kat yüksekliği
    "brick":       {"bay_m": 3.6, "floor_m": 4.0},   # Fen-Edebiyat: kırmızı tuğla + beton bant
    "frame_brick": {"bay_m": 3.6, "floor_m": 4.0},   # mühendislik/İİBF: beton karkas + kırmızı tuğla dolgu
    "brut_light":  {"bay_m": 3.6, "floor_m": 4.0},   # Mimarlık/Spor: açık kalıp izli brüt beton, dar pencere
    "band_light":  {"bay_m": 3.6, "floor_m": 4.0},   # Kütüphane/Rektörlük: açık beton + şerit pencere
    "stone_glass": {"bay_m": 3.0, "floor_m": 4.0},   # Enformatik: bej kesme taş + yeşil çerçeveli cam
    "glass_green": {"bay_m": 1.8, "floor_m": 4.0},   # Teknokent: yeşil tonlu cam paneller
    "lojman":      {"bay_m": 3.0, "floor_m": 3.0},   # kampüs lojmanları: sarımsı tuğla, ahşap pencere, beşik çatı
    "residential": {"bay_m": 3.0, "floor_m": 3.2},   # kampüs dışı konut: sıva
    "modern":      {"bay_m": 1.8, "floor_m": 4.0},   # kampüs dışı ofis/AVM: mavi-gri cam
    "plain":       {"bay_m": 3.0, "floor_m": 3.0},   # küçük yapı / sundurma: penceresiz beton
}
PITCHED = {"lojman"}   # beşik çatılı görünümler (ayak izi dikdörtgene yakınsa)
ROOF_TILE_M = 4.0
RESIDENTIAL = {"apartments", "house", "detached", "semidetached_house", "residential", "terrace"}
MODERN = {"office", "commercial", "retail", "industrial", "train_station", "transportation", "hotel"}

_rules_f = ROOT / "building_looks.json"
RULES = [(re.compile(r["ad"], re.I), r["gorunum"]) for r in json.loads(_rules_f.read_text(encoding="utf-8"))] if _rules_f.exists() else []

def style_of(props, area_m2, in_campus):
    t, nm = props.get("type") or "", props.get("name") or ""
    if area_m2 < 60: return "plain"
    for rx, look in RULES:   # fotoğrafa dayalı kurallar (OSM tür etiketinden önce: ör. Fizik building=roof yanlış etiketli)
        if nm and rx.search(nm): return look
    if t in ("roof", "greenhouse", "shed", "garage", "garages", "kiosk", "hut"): return "plain"
    # --- varsayılanlar (TAHMİN) ---
    if in_campus:
        if t in ("house", "detached", "semidetached_house", "apartments"): return "lojman"   # lojman fotoğrafına göre genelleme
        if t in MODERN: return "glass_green"
        return "frame_brick"   # en sık görülen Çinici dili: beton karkas + kırmızı tuğla (yurtlar dahil, fotoğraf bulunamadı)
    if t in MODERN or re.search(r"AVM|Bakanlığı|Başkanlığı|Genel Müdürlüğü|Genel Merkez|Plaza|Kule", nm): return "modern"
    return "residential"

# --- dokular (dizi satır 0 = karenin ALTI; görüntüye çevirirken ters çevrilir) ---------------------------------------
def _noise(rng, amp):
    n = rng.normal(0, 1, (PX // 8, PX // 8))
    return np.kron(n, np.ones((8, 8)))[:PX, :PX] * amp * 0.6 + rng.normal(0, amp * 0.4, (PX, PX))

CONCRETE = (202, 196, 186)   # fotoğraflarda açık, sıcak gri-bej
def _concrete(rng, base=CONCRETE, boards=True):
    img = np.empty((PX, PX, 3)); img[:] = base
    img += _noise(rng, 6)[..., None]
    if boards:   # ahşap kalıp izi: ~15 cm'lik yatay tahta bantları
        h = PX // 26
        for r0 in range(0, PX, h):
            img[r0:r0 + h] += rng.normal(0, 4); img[r0] -= 9
    return img

def _bricks(rng, base, mortar, brick_m=(0.25, 0.075), m_per_px=3.6 / PX):
    """Şaşırtmalı (running bond) tuğla örgüsü; her tuğla hafif farklı tonda."""
    img = np.empty((PX, PX, 3)); img[:] = mortar
    bw, bh = max(4, round(brick_m[0] / m_per_px)), max(3, round(brick_m[1] / m_per_px))
    for row, y in enumerate(range(0, PX, bh)):
        off = (bw // 2) * (row % 2)
        for x in range(-off, PX, bw):
            c = np.array(base) + rng.normal(0, 10) + rng.normal(0, 4, 3)
            img[y:y + bh - 1, max(0, x):max(0, x + bw - 1)] = c
    return img

def _rect(img, mx, my, x0, x1, y0, y1, color, jitter=0, rng=None):
    a, b = int(x0 / mx), int(x1 / mx); c, d = int(y0 / my), int(y1 / my)
    if isinstance(color, np.ndarray) and color.ndim == 3: img[c:d, a:b] = color[c:d, a:b]
    else: img[c:d, a:b] = color
    if jitter: img[c:d, a:b] += rng.normal(0, jitter, (d - c, b - a, 1))

def _glass(img, mx, my, x0, x1, y0, y1, rng, tint=(52, 62, 72)):
    _rect(img, mx, my, x0, x1, y0, y1, tint, 3, rng)
    c, d, a, b = int(y0 / my), int(y1 / my), int(x0 / mx), int(x1 / mx)
    img[c:d, a:b] += np.linspace(0, 22, d - c)[:, None, None]   # gökyüzü yansıması yukarı doğru açılır

RED_BRICK, MORTAR = (172, 86, 56), (188, 178, 164)
def texture(style, seed=1):
    rng = np.random.default_rng(seed)
    s = STYLES[style]; mx, my = s["bay_m"] / PX, s["floor_m"] / PX
    if style == "brick":   # tuğla duvar, döşeme hizasında beton bant, aks başına dar düşey yarık pencere
        img = _bricks(rng, RED_BRICK, MORTAR, m_per_px=mx)
        _rect(img, mx, my, 0, 3.6, 3.6, 4.0, CONCRETE, 4, rng)
        _glass(img, mx, my, 1.55, 2.05, 0.6, 3.3, rng)
        _rect(img, mx, my, 1.45, 1.55, 0.6, 3.3, (150, 145, 136), 2, rng)   # yarığın beton pervazı
        _rect(img, mx, my, 2.05, 2.15, 0.6, 3.3, (150, 145, 136), 2, rng)
    elif style == "frame_brick":   # beton pilastr + döşeme bandı karkası, alt tuğla dolgu, üstte pencere
        img = _concrete(rng)
        bricks = _bricks(rng, RED_BRICK, MORTAR, m_per_px=mx)
        _rect(img, mx, my, 0.3, 3.3, 0.0, 1.1, bricks)                       # parapet: tuğla dolgu
        _glass(img, mx, my, 0.45, 3.15, 1.2, 3.1, rng)
        for xm in (1.3, 2.25):
            _rect(img, mx, my, xm, xm + 0.08, 1.2, 3.1, (175, 170, 160), 2, rng)   # kayıt
        _rect(img, mx, my, 0.3, 3.3, 1.1, 1.2, (150, 145, 136), 2, rng)     # denizlik gölgesi
        _rect(img, mx, my, 0.0, 0.3, 0.0, 4.0, (214, 208, 198), 3, rng)     # öne çıkan pilastr
        _rect(img, mx, my, 3.3, 3.6, 0.0, 4.0, (214, 208, 198), 3, rng)
        _rect(img, mx, my, 0.0, 3.6, 3.4, 4.0, (208, 202, 192), 3, rng)     # döşeme alnı
    elif style == "brut_light":   # dar düşey pencere, iki yanda derin beton fin
        img = _concrete(rng)
        _glass(img, mx, my, 1.25, 2.35, 0.9, 3.3, rng)
        _rect(img, mx, my, 1.05, 1.25, 0.9, 3.3, (150, 145, 136), 2, rng)
        _rect(img, mx, my, 0.0, 0.3, 0.0, 4.0, (214, 208, 198), 3, rng)
        _rect(img, mx, my, 3.3, 3.6, 0.0, 4.0, (214, 208, 198), 3, rng)
        _rect(img, mx, my, 0.3, 0.42, 0.0, 4.0, (156, 150, 141), 2, rng)
        _rect(img, mx, my, 0.0, 3.6, 3.55, 4.0, (190, 184, 174), 3, rng)
    elif style == "band_light":   # beton korkuluk + sürekli şerit pencere
        img = _concrete(rng, boards=False)
        _glass(img, mx, my, 0.0, 3.6, 1.1, 3.2, rng, (44, 52, 60))
        for xm in (0.0, 1.2, 2.4):
            _rect(img, mx, my, xm, xm + 0.1, 1.1, 3.2, (186, 180, 170), 2, rng)
        _rect(img, mx, my, 0.0, 3.6, 1.0, 1.1, (150, 145, 136), 2, rng)
    elif style == "stone_glass":   # kesme taş bloklar + yeşil çerçeveli düşey cam şerit
        img = _bricks(rng, (214, 198, 166), (196, 182, 152), brick_m=(0.6, 0.3), m_per_px=mx)
        _rect(img, mx, my, 1.05, 1.95, 0.0, 4.0, (70, 112, 92), 0, rng)    # yeşil çerçeve
        _glass(img, mx, my, 1.12, 1.88, 0.0, 4.0, rng, (60, 80, 82))
        for ym in (1.0, 2.0, 3.0):
            _rect(img, mx, my, 1.05, 1.95, ym, ym + 0.06, (70, 112, 92))
    elif style == "glass_green":   # yeşil tonlarında rastgele cam paneller, beyaz çerçeve
        img = np.empty((PX, PX, 3)); img[:] = (228, 230, 228)
        for (y0, y1) in ((0.1, 1.9), (2.05, 3.9)):
            g = rng.choice([(46, 120, 70), (70, 150, 90), (34, 92, 60), (96, 160, 110)])
            _glass(img, mx, my, 0.08, 1.72, y0, y1, rng, g)
    elif style == "lojman":   # sarımsı (buff) tuğla, ahşap çerçeveli pencere
        img = _bricks(rng, (206, 168, 116), (214, 196, 168), m_per_px=mx)
        _rect(img, mx, my, 0.8, 2.2, 0.8, 2.3, (112, 70, 38))
        _glass(img, mx, my, 0.9, 2.1, 0.9, 2.2, rng, (58, 64, 70))
        _rect(img, mx, my, 1.47, 1.53, 0.9, 2.2, (112, 70, 38))
    elif style == "modern":
        img = np.empty((PX, PX, 3)); img[:] = (120, 125, 130)
        _glass(img, mx, my, 0.06, 1.74, 0.7, 3.94, rng, (64, 88, 108))
        _rect(img, mx, my, 0.0, 1.8, 0.0, 0.7, (92, 98, 104), 2, rng)
    elif style == "residential":
        img = np.empty((PX, PX, 3)); img[:] = (222, 212, 192); img += _noise(rng, 4)[..., None]
        _rect(img, mx, my, 0.85, 2.15, 0.85, 2.35, (240, 238, 232))
        _glass(img, mx, my, 0.95, 2.05, 0.95, 2.25, rng, (58, 66, 74))
        _rect(img, mx, my, 0.8, 2.2, 0.78, 0.88, (200, 196, 188))
    else:   # plain
        img = _concrete(rng, boards=False)
    return Image.fromarray(np.clip(img[::-1], 0, 255).astype(np.uint8))

def roof_texture(kind="flat", seed=7):
    rng = np.random.default_rng(seed)
    if kind == "tile":   # kiremit: kahve-kırmızı sıralar (lojman fotoğrafı)
        img = np.empty((PX, PX, 3)); img[:] = (140, 78, 54)
        for r0 in range(0, PX, 12): img[r0:r0 + 2] -= 28
        img += _noise(rng, 7)[..., None]
    else:   # düz çatı: koyu gri çakıl/membran (uydu görüntüsüne bakıldı)
        img = np.empty((PX, PX, 3)); img[:] = (98, 95, 91); img += _noise(rng, 9)[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

def material(img, name):
    return trimesh.visual.material.PBRMaterial(name=name, baseColorTexture=img, metallicFactor=0.0, roughnessFactor=0.92)

# --- geometri (z-yukarı; doğu, kuzey, yukarı) ------------------------------------------------------------------------
def walls(pp, base, hgt, style):
    """Duvar dörtgenleri + UV. Her duvarda aks sayısı ve kat sayısı tam sayıya yuvarlanır (yarım pencere olmasın)."""
    s = STYLES[style]
    ring = np.array(orient(pp, 1.0).exterior.coords)   # saat yönü tersi -> dışa bakan normaller
    nf = max(1, round(hgt / s["floor_m"]))
    V, UV, F = [], [], []
    for (x0, y0), (x1, y1) in zip(ring[:-1], ring[1:]):
        L = np.hypot(x1 - x0, y1 - y0)
        if L < 1e-3: continue
        nb = max(1, round(L / s["bay_m"]))
        k = len(V)
        V += [(x0, y0, base), (x1, y1, base), (x1, y1, base + hgt), (x0, y0, base + hgt)]
        UV += [(0, 0), (nb, 0), (nb, nf), (0, nf)]
        F += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
    return V, UV, F

def roof(pp, top):
    v2, f = trimesh.creation.triangulate_polygon(pp)
    V = np.column_stack([v2, np.full(len(v2), top)])
    if trimesh.Trimesh(V, f, process=False).face_normals[:, 2].mean() < 0: f = f[:, ::-1]   # yukarı baksın
    return V.tolist(), (v2 / ROOF_TILE_M).tolist(), f.tolist()

def gable(pp, top, style):
    """Ayak izi dikdörtgene yakınsa beşik çatı: (çatı V/UV/F, alın üçgenleri V/UV/F) yoksa None.
    Mahya uzun kenara paralel, eğim ~20°, 0,4 m saçak taşması."""
    mrr = pp.minimum_rotated_rectangle
    if mrr.geom_type != "Polygon" or pp.area / mrr.area < 0.8: return None
    c = np.array(mrr.exterior.coords)[:4]
    e1, e2 = c[1] - c[0], c[2] - c[1]
    if np.linalg.norm(e1) < np.linalg.norm(e2): c = np.roll(c, -1, axis=0); e1, e2 = e2, e1   # c0->c1 uzun kenar
    ul, us = e1 / np.linalg.norm(e1), e2 / np.linalg.norm(e2)
    short = np.linalg.norm(e2); rise = min(3.0, short / 2 * np.tan(np.radians(20)))
    o = 0.4   # saçak
    A, B = c[0] - ul * o - us * o, c[1] + ul * o - us * o
    C, D = c[2] + ul * o + us * o, c[3] - ul * o + us * o
    Ra, Rb = (c[0] + c[3]) / 2 - ul * o, (c[1] + c[2]) / 2 + ul * o
    z0, z1 = top, top + rise
    P = lambda p, z: (float(p[0]), float(p[1]), z)
    RV = [P(A, z0), P(B, z0), P(Rb, z1), P(Ra, z1), P(C, z0), P(D, z0), P(Ra, z1), P(Rb, z1)]
    RF = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)]
    RU = [(v[0] / ROOF_TILE_M, v[1] / ROOF_TILE_M) for v in RV]
    # alın üçgenleri (duvar malzemesi): kısa kenarlarda, saçaksız
    g0, g1 = (c[0] + c[3]) / 2, (c[1] + c[2]) / 2
    GV = [P(c[3], z0), P(c[0], z0), P(g0, z1), P(c[1], z0), P(c[2], z0), P(g1, z1)]
    s = STYLES[style]; sh = short / s["bay_m"]
    GU = [(0, 0), (sh, 0), (sh / 2, rise / s["floor_m"]), (0, 0), (sh, 0), (sh / 2, rise / s["floor_m"])]
    GF = [(0, 1, 2), (3, 4, 5)]
    cen = np.array([*mrr.centroid.coords[0], z0])
    def outward(V, F):   # her üçgeni bina merkezinden dışa baktır
        V = np.array(V); out = []
        for f in F:
            n = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
            out.append(f if np.dot(n, V[list(f)].mean(0) - cen) >= 0 else f[::-1])
        return out
    return (RV, RU, outward(RV, RF)), (GV, GU, outward(GV, GF))
