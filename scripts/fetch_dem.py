"""Copernicus GLO-30 DEM'den BBOX penceresini okur -> data/dem.npz (yükseklik ızgarası + coğrafi konum)
Kaynak: AWS Open Data "copernicus-dem-30m" (COG; sadece gereken pencere HTTP range ile okunur).
Lisans/atıf: © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS
by the European Union and ESA; all rights reserved.
Not: GLO-30 bir DSM'dir (bina/ağaç tepeleri dahil), 30 m çözünürlükte bu etki yumuşar ama tamamen kaybolmaz.
Kullanım: python scripts/fetch_dem.py
"""
import math, sys, pathlib
import numpy as np, rasterio
from rasterio.windows import from_bounds
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from config import BBOX

MARGIN = 0.003   # derece; zemin kenarı binaların biraz dışına taşsın
W, S, E, N = BBOX[0] - MARGIN, BBOX[1] - MARGIN, BBOX[2] + MARGIN, BBOX[3] + MARGIN
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

def tile_url(lat, lon):
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    name = f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"
    return f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"

if math.floor(S) != math.floor(N) or math.floor(W) != math.floor(E):
    raise SystemExit("BBOX birden fazla 1°x1° karoya taşıyor; karoları birleştirme henüz yok")
url = tile_url(math.floor(S), math.floor(W))
print("Okunuyor:", url)
with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
    with rasterio.open(url) as src:
        win = from_bounds(W, S, E, N, src.transform).round_offsets().round_lengths()
        h = src.read(1, window=win).astype(np.float32)
        t = src.window_transform(win)
# t: piksel (sütun, satır) sol-üst köşe -> (lon, lat). Piksel merkezleri yarım adım içeride.
lon0, lat0 = t.c + t.a / 2, t.f + t.e / 2   # ilk pikselin (kuzeybatı) merkezi
np.savez_compressed(DATA / "dem.npz", h=h, lon0=lon0, lat0=lat0, dlon=t.a, dlat=t.e)
print(f"{h.shape[1]}x{h.shape[0]} piksel, yükseklik {h.min():.1f}–{h.max():.1f} m -> data/dem.npz")
