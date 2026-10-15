# Önemli yapıların elle modellenmesi (Blender)

`landmarks.json` hangi yapının elle modelleneceğini tanımlar. Bir yapının `file` dosyası (ör. `kutuphane.glb`)
bu klasörde olduğu anda `build_gltf.py` o yapının kutu bloğunu kaldırır ve viewer modeli yerine koyar.
Dosya yoksa eski blok görünmeye devam eder; yani modeller tek tek eklenebilir.

## Akış

1. Referans paketlerini üret (bina verisi veya arazi değiştikçe yeniden çalıştır):

       python scripts/export_landmark_refs.py

   Çıktı `ref/<key>_ref.glb` ve `ref/<key>_ref.json` olur. JSON'da anchor koordinatı, zemin kotu, mevcut ayak izi
   (doğu/kuzey metre) ve şu anki tahmini yükseklik bulunur.
2. Blender'da **File > Import > glTF 2.0** ile `ref/<key>_ref.glb` dosyasını aç. Gelen nesneler:
   - `HEDEF_*` (turuncu): yerine geçeceğin bina(lar), şu anki tahmini yükseklikleriyle
   - `ALAN_SINIRI` (sarı): bina olmayan yapıların OSM sınırı (Devrim)
   - `KOMSU_BINALAR` (gri), `ARAZI` (yeşil, 400×400 m), `KUZEY` (kırmızı ok)
3. Eksenler: **+X doğu, +Y kuzey, +Z yukarı, 1 birim = 1 m**. Orijin yapının merkezinde, z=0 ise o noktadaki zemin.
   Modeli bu orijine göre kur. Yamaçtaki yapılarda temeli z<0'a kadar indir (arazi parçası rehberin).
4. Dışa aktarmadan önce referans nesnelerini sil ya da gizle. Ardından **File > Export > glTF 2.0**:
   biçim *glTF Binary (.glb)*, *Include > Selected Objects*, *Transform > +Y Up* (varsayılan), *Apply Modifiers*.
   Kaydedeceğin yer: `models/<file>`, ör. `models/kutuphane.glb`.
5. `python scripts/build_gltf.py` çalıştır, sonra viewer'ı yenile.

## Ayarlar (`landmarks.json`)

- `anchor`: konumun kaynağı olan OSM nesnesi (modelin orijini onun merkezidir)
- `replace`: kutu bloğu kaldırılacak bina id'leri; `replace_inside: true` alanın içindeki tüm binaları ekler
- `rot_deg` (dikey eksende, yukarıdan bakınca saat yönünün tersine), `scale`: hizalama düzeltmesi
- `collision: false`: eski ayak izinin çarpışmasını kapatır (model şekli farklıysa, ör. altından geçilen kapı)

## Kurallar

- Google 3D Tiles, Street View veya uydu görüntüsünden ölçü alma, doku kopyalama ya da iz sürme yok.
- Doku için kendi fotoğrafların veya CC0 dokular (ör. ambientCG, Poly Haven) kullanılabilir.
  Mapillary görüntüleri sadece bakıp anlamak için; doku olarak kullanılmaz.
- ODTÜ kampüs haritası ve Salt Research planları ölçü/biçim referansıdır, görselleri modele kopyalanmaz.
- Bütçe: model başına en fazla ~50k üçgen, dokular en fazla 2048 px. Malzeme olarak Principled BSDF kullan.
