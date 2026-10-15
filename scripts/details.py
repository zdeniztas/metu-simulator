"""Fotoğraflarda görülen ayırt edici mimari detaylar: prosedürel geometri (build_gltf.py kullanır).
Fotoğraflara sadece BAKILDI (kaynaklar building_looks.json / CLAUDE.md); hiçbir görsel doku olarak kullanılmaz.
- Devrim Stadyumu: koşu pistinin bir uzun kenarında basamaklı beton tribün + basamaklara boyalı beyaz "DEVRİM" yazısı
- Fizik / Kafeterya: düz çatıda küçük koyu camlı piramit tepe pencereleri
- Kütüphane: köşelerde silindirik camlı merdiven kuleleri
- Rektörlük: üst katta silindirik çıkmalar + zemin katta geri çekilmiş cam ve kolonlar (pilotis)
Çarpışma (viewer/footprints.json) değişmez: detaylar ayak izine eklenmez. Koordinatlar z-yukarı (doğu, kuzey, yukarı).
"""
import re
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, Point, shape
from shapely.geometry.polygon import orient
from common import _overpass_geoms, proj
import facades

# ad regex -> detaylar (ilk eşleşen). min_alan: aynı adlı küçük parçaları (ör. Fizik'in sundurması) eler.
RULES = [
    (re.compile(r"^Fizik Bölümü$"), {"tepe_pencere": 4, "min_alan": 500}),   # SALT 123456789/80124 (Fizik)
    (re.compile(r"^Kafeterya$"), {"tepe_pencere": 4}),                         # Commons: METU Cafeteria.jpg
    (re.compile(r"^ODTÜ Kütüphane$"), {"kule": 4}),                            # Commons: METU Library serisi
    (re.compile(r"^Rektörlük$"), {"cikma": True, "pilotis": True}),            # Commons: METU, Rectorate Building
]
STADIUM = "way/430982885"   # Devrim Stadyumu (leisure=stadium); tribün OSM'de haritalanmamış
GLASS_M = 1.5               # cam doku karesi (kayıt aralığı) metre
GF_M, RECESS_M = 4.0, 2.0   # pilotis: zemin kat yüksekliği, cam geri çekilmesi

def features(props, area_m2):
    nm = props.get("name") or ""
    for rx, d in RULES:
        if rx.search(nm) and area_m2 >= d.get("min_alan", 0): return d
    return {}

# --- dokular -----------------------------------------------------------------------------------------------------
def glass_texture(seed=3):
    """Koyu cam + ince metal kayıtlar; bir kare = GLASS_M x GLASS_M."""
    rng = np.random.default_rng(seed); P = facades.PX
    img = np.empty((P, P, 3)); img[:] = (40, 50, 60)
    img += np.linspace(26, 0, P)[:, None, None]          # üstte gökyüzü yansıması (dizi satır 0 = üst)
    img += rng.normal(0, 2, (P, P, 1))
    k = P // 24
    img[:k] = img[-k:] = img[:, :k] = img[:, -k:] = (88, 92, 96)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

def _letter(ch, w, h, sw):
    """Blok harf maskesi (L kipi). İ'nin noktası harf kutusunun üstüne taşar -> maske yüksekliği 1.3 h."""
    top = int(0.3 * h); m = Image.new("L", (w, h + top), 0); d = ImageDraw.Draw(m)
    box = lambda x0, y0, x1, y1: d.rectangle([x0, top + y0, x1, top + y1], fill=255)
    line = lambda a, b, c, e: d.line([(a, top + b), (c, top + e)], fill=255, width=sw)
    if ch == "D":   # sol kenar maske dışında kalan yuvarlatılmış dikdörtgen -> sağda kavis, solda dik köşe
        d.rounded_rectangle([-w, top, w - 1, top + h - 1], radius=int(h * 0.45), outline=255, width=sw)
        box(0, 0, sw, h)
    elif ch == "E":
        box(0, 0, sw, h); box(0, 0, w, sw); box(0, h - sw, w, h); box(0, (h - sw) // 2, int(w * 0.85), (h + sw) // 2)
    elif ch == "V":
        line(sw // 2, 0, w // 2, h - sw // 3); line(w - sw // 2, 0, w // 2, h - sw // 3)
    elif ch == "R":
        bh = int(h * 0.55)
        d.rounded_rectangle([-w, top, int(w * 0.95), top + bh], radius=bh // 2, outline=255, width=sw)
        box(0, 0, sw, h); line(int(w * 0.45), bh - sw // 2, w - sw // 2, h)
    elif ch == "İ":
        box(0, 0, w, h); box(0, -int(0.28 * h), w, -int(0.1 * h))
    elif ch == "M":
        box(0, 0, sw, h); box(w - sw, 0, w, h)
        line(sw // 2, 0, w // 2, int(h * 0.65)); line(w - sw // 2, 0, w // 2, int(h * 0.65))
    return m

def grandstand_texture(L, wmax, ppm=24, text="DEVRİM", seed=5):
    """Tribün açılımı: u = tribün boyu (0..L), v = 'açılım' koordinatı w (0..wmax, yukarı). Gri beton + beyaz harfler."""
    rng = np.random.default_rng(seed)
    W, H = int(L * ppm), int(wmax * ppm)
    img = np.empty((H, W, 3)); img[:] = (168, 166, 160)
    n = rng.normal(0, 1, (H // 6 + 1, W // 6 + 1))
    img += np.kron(n, np.ones((6, 6)))[:H, :W, None] * 5 + rng.normal(0, 3, (H, W, 1))
    hc = int(0.68 * H); sw = int(0.17 * hc); lw = int(0.85 * hc); gap = int(0.3 * hc)   # büyük harf boyu, çizgi, harf eni
    widths = [sw if c == "İ" else lw for c in text]
    x = (W - sum(widths) - gap * (len(text) - 1)) // 2
    ytop = H - int(0.06 * H) - hc - int(0.3 * hc)   # maskenin üstü (İ noktası payı dahil)
    mask = Image.new("L", (W, H), 0)
    for c, w in zip(text, widths):
        mask.paste(_letter(c, w, hc, sw), (x, ytop)); x += w + gap
    a = np.asarray(mask, float)[..., None] / 255 * (0.9 + 0.1 * rng.random((H, W, 1)))   # boya hafif aşınmış
    img = img * (1 - a) + np.array((238, 238, 232)) * a
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))   # satır 0 = üst = w max

TEXTURES = {"glass_dark": glass_texture}   # "tribun" dokusu geometriyle birlikte üretilir (boyu stadyuma bağlı)

# --- geometri yardımcıları ----------------------------------------------------------------------------------------
class Mesh:
    """parça adı -> (V, UV, F); quad() üçgen sırasını verilen dış normale göre çevirir."""
    def __init__(self): self.parts = {}
    def quad(self, key, P, UV, nrm):
        V, U, F = self.parts.setdefault(key, ([], [], []))
        P = [tuple(map(float, p)) for p in P]; k = len(V); V += P; U += [tuple(map(float, u)) for u in UV]
        tri = [(0, 1, 2), (0, 2, 3)] if len(P) == 4 else [(0, 1, 2)]
        a, b, c = (np.array(P[i]) for i in tri[0])
        if np.dot(np.cross(b - a, c - a), nrm) < 0: tri = [t[::-1] for t in tri]
        F += [tuple(i + k for i in t) for t in tri]
    def tri(self, key, P, UV, nrm):
        self.quad(key, P, UV, nrm)
    def poly(self, key, pp, z, up, tile=facades.ROOF_TILE_M):
        """Yatay çokgen (shapely, x/y) z kotunda; up=True yukarı, False aşağı bakar."""
        v2, f = facades.trimesh.creation.triangulate_polygon(pp)
        V, U, F = self.parts.setdefault(key, ([], [], [])); k = len(V)
        V += [(float(x), float(y), z) for x, y in v2]; U += [(x / tile, y / tile) for x, y in v2]
        for t in f:
            a, b, c = (np.array([*v2[i], 0.0]) for i in t)
            F.append(tuple(int(i) + k for i in (t if (np.cross(b - a, c - a)[2] > 0) == up else t[::-1])))
    def items(self): return [(k, *v) for k, v in self.parts.items() if v[2]]

def _cyl(m, key, c, r, z0, z1, a0, a1, e, n, nseg, uw, uh, caps=None):
    """Silindir yüzeyi: c + r(cos a e + sin a n), a0..a1. uw/uh: doku karesi eni/boyu (m). caps: (alt, üst) parça adları."""
    A = np.linspace(a0, a1, nseg + 1)
    pts = [np.asarray(c) + r * (np.cos(a) * e + np.sin(a) * n) for a in A]
    for i in range(nseg):
        p, q = pts[i], pts[i + 1]; mid = (p + q) / 2 - c
        u0, u1 = r * (A[i] - a0) / uw, r * (A[i + 1] - a0) / uw
        m.quad(key, [(*p, z0), (*q, z0), (*q, z1), (*p, z1)], [(u0, 0), (u1, 0), (u1, (z1 - z0) / uh), (u0, (z1 - z0) / uh)],
               (*mid, 0))
    if caps:
        ring = Polygon(pts if a1 - a0 >= 2 * np.pi - 1e-6 else pts + [np.asarray(c)])
        if caps[0]: m.poly(caps[0], ring, z0, False)
        if caps[1]: m.poly(caps[1], ring, z1, True)

def _farthest(points, k):
    """Birbirinden en uzak k nokta (açgözlü)."""
    if not points: return []
    P = np.array(points); c = P.mean(0); sel = [int(np.argmax(((P - c) ** 2).sum(1)))]
    while len(sel) < min(k, len(P)):
        d = np.min([((P - P[s]) ** 2).sum(1) for s in sel], axis=0); sel.append(int(np.argmax(d)))
    return [P[s] for s in sel]

def _axes(pp):
    """Ayak izinin ana yönleri (en küçük döndürülmüş dikdörtgen): birim e (uzun), n."""
    c = np.array(pp.minimum_rotated_rectangle.exterior.coords)[:3]
    e = c[1] - c[0]; e /= np.linalg.norm(e); return e, np.array([-e[1], e[0]])

# --- bina detayları -------------------------------------------------------------------------------------------------
def skylights(m, pp, top, count, a=3.2, h=1.5, curb=0.35):
    """Düz çatıya kare tabanlı koyu cam piramitler (bina eksenine hizalı) + beton bordür."""
    inner = pp.buffer(-(a + 1.5))
    if inner.is_empty: return 0
    e, n = _axes(pp); x0, y0, x1, y1 = inner.bounds
    grid = [(x, y) for x in np.arange(x0, x1 + 1e-6, 5.0) for y in np.arange(y0, y1 + 1e-6, 5.0) if inner.contains(Point(x, y))]
    pts = _farthest(grid, count)
    for c in pts:
        C = [c + s * a / 2 * e + t * a / 2 * n for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        zb, zt = top + curb, top + curb + h
        for i in range(4):   # bordür yan yüzü + piramit üçgeni
            p, q = C[i], C[(i + 1) % 4]; out = (p + q) / 2 - c
            m.quad("plain", [(*p, top), (*q, top), (*q, zb), (*p, zb)], [(0, 0), (a / 3, 0), (a / 3, curb / 3), (0, curb / 3)], (*out, 0))
            sl = np.hypot(a / 2, h) / GLASS_M
            m.tri("glass_dark", [(*p, zb), (*q, zb), (*c, zt)], [(0, 0), (a / GLASS_M, 0), (a / 2 / GLASS_M, sl)], (*out, 1.0))
    return len(pts)

def towers(m, pp, base, top, count, r=3.2, over=2.5):
    """Köşelerde silindirik camlı merdiven kuleleri: dönük dikdörtgen köşesine en yakın ayak izi köşesi, biraz içeride."""
    ring = np.array(pp.exterior.coords)[:-1]; cen = np.array(pp.centroid.coords[0])
    corners = np.array(pp.minimum_rotated_rectangle.exterior.coords)[:4]
    used = []
    for k in corners:
        v = ring[np.argmin(((ring - k) ** 2).sum(1))]
        if any(np.allclose(v, u) for u in used): continue
        used.append(v)
    for v in used[:count]:
        d = cen - v; c = v + d / np.linalg.norm(d) * 1.2
        zt = top + over
        _cyl(m, "glass_dark", c, r, base, zt - 0.8, 0, 2 * np.pi, np.array([1.0, 0]), np.array([0, 1.0]), 20, GLASS_M, GLASS_M)
        _cyl(m, "plain", c, r, zt - 0.8, zt, 0, 2 * np.pi, np.array([1.0, 0]), np.array([0, 1.0]), 20, 3.0, 3.0, caps=(None, "roof"))
    return len(used[:count])

def bays(m, pp, top, r=1.7, fh=4.0, min_len=25.0, step=9.0, margin=4.0):
    """Üst katta yarım silindir çıkmalar: uzun duvarlar boyunca; doku band_light (bir kat = bir doku karesi)."""
    ring = np.array(orient(pp, 1.0).exterior.coords); k = 0
    for p0, p1 in zip(ring[:-1], ring[1:]):
        L = np.linalg.norm(p1 - p0)
        if L < min_len: continue
        e = (p1 - p0) / L; nout = np.array([e[1], -e[0]])   # saat yönü tersi halkada dış normal sağda
        nb = int((L - 2 * margin) // step) + 1; s0 = (L - (nb - 1) * step) / 2
        for i in range(nb):
            c = p0 + e * (s0 + i * step)
            _cyl(m, "band_light", c, r, top - fh, top, 0, np.pi, e, nout, 10, facades.STYLES["band_light"]["bay_m"], fh,
                 caps=("plain", "roof"))
            k += 1
    return k

def pilotis(m, pp, base, gf=GF_M, recess=RECESS_M, col=0.6, step=6.0):
    """Geri çekilmiş camlı zemin kat + dış hatta kare kolonlar + saçak altı. Duvarlar base+gf'den başlamalı.
    İç halka üretilemezse None (çağıran normal duvara döner)."""
    inner = pp.buffer(-recess, join_style=2)
    if inner.is_empty or inner.geom_type != "Polygon" or inner.area < 0.3 * pp.area: return None
    ring = np.array(orient(inner, 1.0).exterior.coords)
    for p0, p1 in zip(ring[:-1], ring[1:]):   # cam duvar (dışa bakar)
        L = np.linalg.norm(p1 - p0)
        if L < 1e-3: continue
        nrm = np.array([p1[1] - p0[1], -(p1[0] - p0[0])])
        m.quad("glass_dark", [(*p0, base), (*p1, base), (*p1, base + gf), (*p0, base + gf)],
               [(0, 0), (L / GLASS_M, 0), (L / GLASS_M, gf / GLASS_M), (0, gf / GLASS_M)], (*nrm, 0))
    m.poly("plain", pp.difference(inner), base + gf, False, 3.0)   # saçak altı (aşağı bakar)
    ring = np.array(orient(pp, 1.0).exterior.coords); h = col / 2; ncol = 0
    for p0, p1 in zip(ring[:-1], ring[1:]):
        L = np.linalg.norm(p1 - p0)
        if L < 1.5: continue
        e = (p1 - p0) / L; nin = np.array([-e[1], e[0]])
        for s in np.linspace(h, L - h, max(2, round(L / step) + 1)):
            c = p0 + e * s + nin * (h + 0.3)
            if not pp.contains(Point(*c)): continue
            C = [c + h * (s * e + t * nin) for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            for i in range(4):   # kolonun 4 yan yüzü
                p, q = C[i], C[(i + 1) % 4]
                m.quad("plain", [(*p, base), (*q, base), (*q, base + gf), (*p, base + gf)],
                       [(0, 0), (col / 3, 0), (col / 3, gf / 3), (0, gf / 3)], (*((p + q) / 2 - c), 0))
            ncol += 1
    return ncol

# --- Devrim Stadyumu tribünü ----------------------------------------------------------------------------------------
def grandstand(surf, ground, L=80.0, steps=14, tread=0.85, rise=0.42, gap=2.5, k_tread=0.5):
    """Pistin (surfaces 'track' alanı) uzun kenarlarından arazinin yükseldiği tarafa (doğal yamaç = ODTÜ çanağı; TAHMİN)
    basamaklı tribün. Doku açılımı w = yükseklik + k_tread * derinlik: sahadan bakınca rıhtlar tam, basamak yüzleri
    kısalmış görünür. -> (Mesh, doku) | None"""
    g = _overpass_geoms([STADIUM]).get(STADIUM)
    if not g or not surf: return None
    stad = Polygon([(x, -y) for x, y in (proj(*p) for p in shape(g).exterior.coords)])   # (x, z)
    tracks = [Polygon(a["r"][0]) for a in surf["areas"] if a["k"] == "track"]
    tracks = [t for t in tracks if stad.contains(t.centroid)]
    if not tracks: return None
    t = max(tracks, key=lambda p: p.area)
    c = np.array(t.minimum_rotated_rectangle.exterior.coords)[:4]
    if np.linalg.norm(c[1] - c[0]) < np.linalg.norm(c[2] - c[1]): c = np.roll(c, -1, axis=0)
    tc = c.mean(0); best = None
    for p0, p1 in ((c[0], c[1]), (c[2], c[3])):   # iki uzun kenar: 20 m dışarıdaki arazi daha yüksek olan
        o = (p0 + p1) / 2; nn = o - tc; nn -= np.dot(nn, p1 - p0) / np.dot(p1 - p0, p1 - p0) * (p1 - p0); nn /= np.linalg.norm(nn)
        rise_out = float(ground(*(o + 20 * nn)) - ground(*o))
        if best is None or rise_out > best[0]: best = (rise_out, o, nn)
    _, o, nn = best
    # (x, z) düzleminde: sahadan tribüne bakan için sağ yön u = n x yukarı (z = -kuzey olduğundan işaret çevrilir)
    u = np.array([nn[1], -nn[0]]) * -1
    D = gap + steps * tread
    S, Dd = np.meshgrid(np.linspace(-L / 2, L / 2, 17), np.linspace(gap, D, 8))
    G = ground(o[0] + S * u[0] + Dd * nn[0], o[1] + S * u[1] + Dd * nn[1])
    hb = float(ground(o[0] + np.linspace(-L / 2, L / 2, 17) * u[0] + gap * nn[0],
                      o[1] + np.linspace(-L / 2, L / 2, 17) * u[1] + gap * nn[1]).max())
    zb = float(G.min()) - 0.5
    tops = hb + rise * np.arange(1, steps + 1)
    back = float((tops[-1] - G[-1]).min())
    wmax = steps * rise + k_tread * steps * tread
    m = Mesh()
    X = lambda s, d, z: (o[0] + s * u[0] + d * nn[0], -(o[1] + s * u[1] + d * nn[1]), z)   # -> (doğu, kuzey, yukarı)
    N = lambda v: (v[0], -v[1], 0.0)
    s0, s1 = -L / 2, L / 2
    for i in range(steps):
        a, b = gap + i * tread, gap + (i + 1) * tread
        zlo = zb if i == 0 else tops[i - 1]; zt = tops[i]
        wlo = 0.0 if i == 0 else i * rise + k_tread * i * tread
        whi = (i + 1) * rise + k_tread * i * tread; wtop = whi + k_tread * tread
        m.quad("tribun", [X(s0, a, zlo), X(s1, a, zlo), X(s1, a, zt), X(s0, a, zt)],
               [(0, wlo / wmax), (1, wlo / wmax), (1, whi / wmax), (0, whi / wmax)], N(-nn))            # rıht (sahaya bakar)
        m.quad("tribun", [X(s0, a, zt), X(s1, a, zt), X(s1, b, zt), X(s0, b, zt)],
               [(0, whi / wmax), (1, whi / wmax), (1, wtop / wmax), (0, wtop / wmax)], (0, 0, 1))      # basamak yüzü
        for s, sgn in ((s0, -1), (s1, 1)):   # yan duvarlar (sütun sütun)
            m.quad("plain", [X(s, a, zb), X(s, b, zb), X(s, b, zt), X(s, a, zt)],
                   [(a / 3, zb / 3), (b / 3, zb / 3), (b / 3, zt / 3), (a / 3, zt / 3)], N(sgn * u))
    m.quad("plain", [X(s0, D, zb), X(s1, D, zb), X(s1, D, tops[-1]), X(s0, D, tops[-1])],
           [(0, 0), (L / 3, 0), (L / 3, (tops[-1] - zb) / 3), (0, (tops[-1] - zb) / 3)], N(nn))           # arka duvar
    print(f"Devrim tribünü: {steps} basamak x {L:.0f} m, yön (x,z) n={nn.round(2).tolist()}, ön kot {hb:.1f} m, "
          f"arkada araziden en az {back:.1f} m yüksek")
    return m, grandstand_texture(L, wmax)
