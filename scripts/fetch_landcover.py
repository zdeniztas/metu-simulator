"""ESA WorldCover 2021 (10 m arazi örtüsü) BBOX penceresi -> data/worldcover.npz
Kaynak: AWS Open Data "esa-worldcover" (COG; sadece gereken pencere HTTP range ile okunur).
Lisans/atıf: © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021), CC BY 4.0.
Sınıflar: 10 ağaç örtüsü, 20 çalılık, 30 çayır, 40 tarım, 50 yapılaşmış, 60 çıplak, 80 su ...
Kullanım: python scripts/fetch_landcover.py   (ağaçlar build_gltf.py'de buradan yerleştirilir)
"""
import math, sys, pathlib
import numpy as np, rasterio
from rasterio.windows import from_bounds
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from config import BBOX

W, S, E, N = BBOX
DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
lat0, lon0 = math.floor(S / 3) * 3, math.floor(W / 3) * 3   # karolar 3°x3°, sol-alt köşeyle adlandırılır
if math.floor(N / 3) * 3 != lat0 or math.floor(E / 3) * 3 != lon0:
    raise SystemExit("BBOX birden fazla WorldCover karosuna taşıyor; birleştirme henüz yok")
name = f"ESA_WorldCover_10m_2021_v200_N{lat0:02d}E{lon0:03d}_Map"
url = f"/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{name}.tif"
print("Okunuyor:", url)
with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
    with rasterio.open(url) as src:
        win = from_bounds(W, S, E, N, src.transform).round_offsets().round_lengths()
        c = src.read(1, window=win)
        t = src.window_transform(win)
np.savez_compressed(DATA / "worldcover.npz", c=c, lon0=t.c + t.a / 2, lat0=t.f + t.e / 2, dlon=t.a, dlat=t.e)
vals, cnt = np.unique(c, return_counts=True)
print(f"{c.shape[1]}x{c.shape[0]} piksel; sınıf payları:", {int(v): f"%{100 * n / c.size:.0f}" for v, n in zip(vals, cnt)})
