# ODTÜ 3D Kampüs — Claude Code devir notu

Amaç: ODTÜ (METU, Ankara) kampüsünün, internet verisiyle (Ankara'ya gitmeden) kurulmuş 3D modeli + üstünde görev tabanlı
GTA-tarzı bir web simülatörü. Ticari değil, kişisel proje.

## Kurallar (araştırmadan çıkanlar)
- Google Photorealistic 3D Tiles'tan model ÇIKARMA/indirme/izleme YOK (Map Tiles API politikası: geodata extraction, offline use,
  türetme yasak). Google sadece canlı görselleştirme içindir.
- Kaynaklar: OpenStreetMap (ODbL, atıf zorunlu), Overture Maps buildings (ODbL), Copernicus GLO-30 (arazi, 30 m;
  atıf metni README'de).
- Mapillary: lisans belirsiz (CC BY-SA ama kullanım şartları türev çalışma/toplu indirmeyi kısıtlıyor) → doku için riskli.
- OSM'e eklerken Google görüntüsünden çizim yapma.

## Durum
- 2026-10-15: boru hattı GERÇEK veriyle yerelde çalıştı. OSM 527 bina (155 farklı isim), 245 POI; Overture +187 bina
  (hepsi Microsoft ML ayak izi, yüksekliksiz — Overture'daki yükseklikler zaten OSM kaynaklı). Toplam 714 bina,
  %95'i varsayılan 9 m (sadece 34 binada OSM height/levels var) → iş 4 önemli.
- viewer tarayıcıda test edildi: yükleniyor, yürüme/görev atlama çalışıyor, 11/11 görev yeri bulunuyor.
  BBOX kuzeyi 39.910'a genişletildi (A1 Kapısı/Bilim Ağacı ~39.908'de) → 995 bina, 471 isimli yer.
  Dikkat: "ODTÜ Bilim Ağacı İlk Yeri" (eski yer, historic=ruins) da var; görev regex'i ^...$ ile asıl heykele sabitli.
  Sağlık Merkezi OSM'de "Mediko".
- Arazi (2026-10-15): scripts/fetch_dem.py, AWS Open Data copernicus-dem-30m kovasından (doğrulandı) N39/E032
  karosunun sadece BBOX+0.003° penceresini okur -> data/dem.npz (140x122 px, 843–1018 m). build_gltf.py bunu
  viewer/terrain.json'a yazar (orijin kotu ~903 m = y 0) ve binaları ayak izinin en düşük zemin noktasına oturtur.
  Viewer arazi mesh'ini ve karakter/kamera/işaret yüksekliğini terrain.json'dan alır (Python ile aynı bilinear).
  GLO-30 bir DSM ama ölçüldü: bina merkezleri çevreden medyan 0,2 m yüksek → yumuşatma gerekmedi.
- Bina çarpışması (2026-10-15): build_gltf.py viewer/footprints.json yazar ({t: çatı kotu, p: [[x,z],...]}).
  Viewer kenarları 32 m'lik ızgarada tutar; oyuncu R=0,4 m daire, ≤0,25 m alt adımlarla hareket + duvar boyunca kayma.
  Başlangıç noktası bina içindeyse en yakın boş noktaya alınır. Görev hedefi bir binanın içindeyse o binanın duvarına
  8 m yaklaşmak yeterli (büyük binalarda merkez r'den uzak kalıyordu). Kamera arada bina varsa: bina oyuncudan
  ≤20 m yüksekse çatının üstüne çıkar, daha yüksekse duvarın önüne yaklaşır. Konsolda window.odtu = {player, tasks, …}.
  Bilinen: bazı ayak izleri üst üste biniyor (OSM/Overture çakışmaları) — çarpışmayı bozmuyor ama arada sıkışan
  boşluklar olabilir; iç avlular (multipolygon iç halkaları) hâlâ yok.
- Overpass aynaları (kumi, private.coffee) 500 veriyor; ana sunucu yük altında 502 → fetch_osm.py üstel geri çekilme
  yapıyor ve ham yanıtları data/raw_*.json'a önbelleğe alıyor (yeniden indirmek için --yenile).

## Çalıştırma
    pip install -r requirements.txt
    python scripts/fetch_osm.py             # binalar, POI, yollar, alanlar (önbellekli; --yenile)
    python scripts/fetch_overture.py        # opsiyonel; -f geojson hata verirse geoparquet + geopandas dene
    python scripts/fetch_dem.py             # arazi (Copernicus GLO-30); yoksa düz zemin
    python scripts/fetch_landcover.py       # ağaç örtüsü (ESA WorldCover); yoksa sadece OSM ağaçları
    python scripts/merge_buildings.py       # gerçek/tahmin yükseklik raporu + data/eksik_yukseklik.csv
    python scripts/build_gltf.py            # out/campus.glb + viewer/{landmarks,terrain,footprints,models,surfaces}.json
    python scripts/export_landmark_refs.py  # opsiyonel: Blender referans paketleri (models/ref/)
    python -m http.server 8000              # sonra http://localhost:8000/viewer/

## Gerçek kampüse benzetme (2026-10-15)
- Uydu görüntüsüyle (Bing, sadece bakıldı) karşılaştırıldı: konumlar doğru; fark ağaç örtüsü ve çatı/cephe görünümüydü.
- Ağaçlar: scripts/fetch_landcover.py (ESA WorldCover 2021 10 m, AWS esa-worldcover, CC BY 4.0; doğrulandı) +
  OSM natural=tree/tree_row -> scripts/trees.py -> viewer/trees.json (~50k). Bina/yol/otopark/su üstüne düşenler
  elenir; ormanda %80 çam. YAKLAŞIM: ODTÜ sınırı (OSM relation/6899696, data/raw_osm_campus.json) içinde
  WorldCover "yapılaşmış" piksellere %35, çayıra %10 olasılıkla ek ağaç (10 m'de bina yanı ağaçlar kayboluyordu).
  Viewer: InstancedMesh, gövde çarpışması, kameraya 8–13 m yakın ağaçlar dither ile kaybolur.
- Cepheler (fotoğraf referanslı, 2026-10-15): Wikimedia Commons (Category:Buildings of Middle East Technical
  University ve alt kategoriler; çoğu SALT/Çinici arşivi, "no known copyright restrictions") ve SALT Research
  kayıtlarındaki (CC BY-NC-ND) fotoğraflara BAKILDI; hiçbir görsel indirilmedi/dokuya çevrilmedi. Gözlemler kural
  olarak building_looks.json'da (ad regex -> görünüm, her satırda kaynak dosya adı). scripts/facades.py 10 görünüm:
  brick (Fen-Edebiyat: kırmızı tuğla + beton bant + yarık pencere), frame_brick (mühendislik/İİBF: açık beton karkas
  + kırmızı tuğla dolgu), brut_light (Mimarlık/Spor/Çarşı), band_light (Kütüphane/Rektörlük/Kafeterya), stone_glass
  (Enformatik), glass_green (Teknokent), lojman (sarımsı tuğla + ahşap pencere + kiremit BEŞİK ÇATI, ayak izi
  dikdörtgene yakınsa), residential/modern (kampüs dışı), plain. Ad kuralları OSM tür etiketinden önce gelir.
  TAHMİN olanlar: yurtlar/konukevleri ve isimsiz kampüs binaları -> frame_brick (yurt fotoğrafı bulunamadı),
  kampüs içi house/apartments -> lojman, kampüs dışı AVM/bakanlık -> modern, renk tonları.
  Detay geometrisi (2026-10-15): scripts/details.py (build_gltf çağırır; kurallar dosyanın başındaki RULES, ad
  regex'i ile). Hepsi prosedürel, foto dokusu yok; çarpışmaya (footprints.json) EKLENMEZ — oyuncu tribünün/kulelerin
  içinden geçebilir. Ek mesh'ler: glass_dark (koyu cam, 1,5 m kayıt), tribun (tek parça açılım dokusu), plain/roof.
    - Devrim tribünü: pist (surfaces 'track', stadyum way/430982885 içinde) uzun kenarlarından 20 m dışarıda arazinin
      daha yüksek olduğu tarafa (batı yamacı; yön TAHMİN — fotoğrafta tribünün hangi kenarda olduğu doğrulanmadı),
      80 m x 14 basamak (0,85 m basamak, 0,42 m rıht). "DEVRİM" PIL ile çizilen blok harfler; doku v = yükseklik +
      0,5 x derinlik, sahadan bakınca soldan sağa okunur. models/devrim.glb eklenirse prosedürel tribün üretilmez.
    - Fizik Bölümü (ana blok, alan ≥500 m²) ve Kafeterya: 4'er piramit tepe penceresi (3,2 m taban, beton bordür).
    - ODTÜ Kütüphane: döndürülmüş dikdörtgen köşelerine en yakın 4 ayak izi köşesinde r=3,2 m camlı silindir kule
      (çatıdan 2,5 m yüksek). Gerçek kulelerin yeri/sayısı yaklaşık (building_looks.json'da "sağır" diye de geçiyor).
    - Rektörlük: ≥25 m duvarlarda 9 m arayla üst katta yarım silindir çıkma (band_light dokusu); zemin kat pilotis
      (duvarlar 4 m'den başlar, 2 m geri çekilmiş cam + 0,6 m kare kolonlar ~6 m arayla + saçak altı).
      Kütüphane'ye pilotis uygulanmadı (fotoğrafta bant pencereli cephe).
  Görülüp henüz uygulanmayanlar: Fizik'teki silindirik merdiven kuleleri, İİBF'deki kare ızgara beton kafes,
  taş kaideler/istinat duvarları.
  Araştırma (alt ajan, metin kaynakları): Çinici'ler 1961–80, ahşap kalıp izli brüt beton + tuğla/taş, dar
  pencere + düşey beton güneş kırıcı, kütüphanede bant pencere, alçak yatay kütleler — Niebrzydowski, Architectus
  2022 (architectus.pwr.edu.pl); gzt.com "Bozkırı yeşerten beton yerleşke"; saltonline.org/en/1757; tr/en.wikipedia.
  Renk tonları kaynaklarda YOK (tahmin). Tuğla dolgu henüz kullanılmadı (hangi binada olduğu belirsiz).
  Kaynaklı yükseklikler height_overrides.json'da: Mimarlık 2 kat, Rektörlük ~5 kat.
  Bulunamayan/yapılmayan: Bilim Ağacı'nın malzeme/boyu ("beyaz" heykel), Devrim tribününün gerçek yeri/ölçüsü,
  Spor Salonu katlanmış plak çatısı (~50x33 m), Çarşı'nın mantar kolonları — models/ ile elle modellenebilir.
- Oynanış: görevlerde süre yok (puan sabit); isimli binanın duvarına 12 m yaklaşınca adı üstte çıkar
  (isimsiz binada içindeki POI adı).

## Sıradaki işler (öncelik sırasıyla)
1. ~~Gerçek veriyle çalıştır; viewer'ı test et, hataları düzelt.~~ (2026-10-15 yapıldı)
2. ~~Görev yerleri / tasks.json regex'leri~~ (2026-10-15 yapıldı, 11/11)
3. ~~Arazi: Copernicus GLO-30~~ (2026-10-15 yapıldı)
4. Yükseklikler — yerel kısım yapıldı (2026-10-15), OSM'e giriş kullanıcıda:
   - merge_buildings.py artık düz 9 m kullanmıyor: kampüsteki etiketli binalardan tür medyanı (university 4 kat,
     dormitory 4,5, apartments 5; ≥3 örnek) > tür tablosu > taban alanı. Kurum binalarında kat 4,0 m
     (config.LEVEL_HEIGHT_INST). İsimde Bölüm/Fakülte/Enstitü/Blok/Amfi/Lab geçen building=yes -> university.
     h_src'de tahmin_* olarak işaretli; gerçek veri hâlâ sadece 39 binada (%4).
   - height_overrides.json (kök): araştırılan değerler için [{"id": "way/..." | "name": "...", "height": m | "levels": n,
     "kaynak": "..."}]; her şeyin önüne geçer, eşleşmeyen satır uyarı verir.
   - data/eksik_yukseklik.csv: gerçek yüksekliği olmayan 658 OSM binası, isimliler + büyük alan önce, OSM linkiyle.
     OSM düzenlemesini Claude göndermez (kullanıcının hesabıyla kamuya yayın). Google görüntüsünden çizme/ölçme yok.
   - Fark edilen OSM etiket hataları: "Fizik Bölümü" building=roof (sundurma) etiketli; "Merkez Mühendislik Binası"
     levels=10/height=30 şüpheli; "TOGO Kuleleri" kule ama commercial 3 kat tahmin ediliyor.
   - Overture'ın eklediği 298 bina Microsoft ML ayak izi; OSM'de yoklar (OSM'e toplu aktarım import kurallarına tabi).
5. Önemli yapılar — hazırlık yapıldı (2026-10-15), modelleme kullanıcıda (bu makinede Blender yok). Akış: models/README.md.
   - models/landmarks.json: 6 yapı (Mimarlık relation/6296521 + Amfi way/431068199, Kütüphane, KKM, Devrim stadium
     alanı way/430982885 [içinde tribün binası haritalanmamış], A1 way/380300013, Bilim Ağacı node/4622453641).
   - scripts/export_landmark_refs.py -> models/ref/<key>_ref.glb/.json (yapı merkezli; hedef + komşu + arazi + kuzey).
   - build_gltf.py: models/<file> varsa o binaların bloğu çıkar, viewer/models.json'a girer; ayak izi (çarpışma,
     collision:false ile kapatılır) ve isim (görevler) kalır. Ortak kod scripts/common.py'de.
   - Uçtan uca geçici kutu modelle test edildi (Kütüphane), test dosyası silindi.
6. ~~Yol/yaya yolu ağı ve yeşil alan/su~~ (2026-10-15 yapıldı)
   - fetch_osm.py ham highway + alan (landuse/natural/leisure/parking/water) yanıtlarını data/raw_osm_{highways,areas}.json'a alır.
   - scripts/surfaces.py (build_gltf çağırır) -> viewer/surfaces.json: arazi kapsamına kırpılmış vektörler
     (890 araç, 784 yaya yolu; orman/çim/park/saha/pist/otopark/su alanları; multipolygon dış−iç birleştirilir;
     tunnel/indoor/yeraltı katı atlanır). Viewer bunları 4096 px'lik kanvasa çizip arazi dokusu yapar (~1,1 px/m).
   - Sınırlar: su düz yüzey değil, araziye boyanmış; yollar dokuda (yükseltisiz), yol ağı oyun mantığında henüz
     kullanılmıyor (araç/yol bulma için surfaces.json hazır). Arazi yoksa doku da yok.
   - Viewer: M tuşu kuşbakışı harita kamerası.
7. Çok oyunculu (Colyseus/Socket.IO) — en sona.
Bilinen sınırlama: OSM multipolygon (iç avlulu) binalarında iç halkalar atlanıyor.
