# ODTÜ 3D Kampüs

OSM + Overture verisinden ODTÜ kampüsünün 3D modelini (glTF) üretir ve three.js'te yürünebilir görev oyunu olarak açar.
Ayrıntılı durum ve yol haritası için CLAUDE.md'ye bak (Claude Code bu dosyayı otomatik okur).

    pip install -r requirements.txt
    python scripts/fetch_osm.py && python scripts/fetch_overture.py && python scripts/fetch_dem.py && python scripts/fetch_landcover.py
    python scripts/merge_buildings.py && python scripts/build_gltf.py
    python -m http.server 8000   # http://localhost:8000/viewer/

BBOX ve başlangıç noktası: config.py. Veri atfı: © OpenStreetMap contributors, Overture Maps Foundation (ODbL).
Arazi: Copernicus DEM GLO-30 — © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under
COPERNICUS by the European Union and ESA; all rights reserved.
Ağaç örtüsü: © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021), CC BY 4.0.
