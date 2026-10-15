"""Overture Maps bina verisini indirir -> data/overture_buildings.geojson  (ODbL)
Önce: pip install overturemaps
"""
import subprocess, sys, pathlib, shutil
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from config import BBOX
out = pathlib.Path(__file__).resolve().parent.parent / "data" / "overture_buildings.geojson"
exe = shutil.which("overturemaps")
if not exe:
    raise SystemExit("overturemaps CLI yok: pip install overturemaps")
cmd = [exe, "download", f"--bbox={BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}", "-f", "geojson", "--type=building", "-o", str(out)]
print(" ".join(cmd)); subprocess.run(cmd, check=True)
print("Kaydedildi:", out)
