"""Ortak ayarlar. Önce çekirdek bölgeyi dene, sonra BBOX'u büyüt."""
# (batı, güney, doğu, kuzey)  — ODTÜ çekirdek bölgesi (yaklaşık; gerekirse düzelt)
BBOX = (32.762, 39.882, 32.795, 39.910)   # kuzey 39.910: A1 Kapısı ve Bilim Ağacı (~39.908) dahil olsun
# Yerel koordinat orijini (metre cinsinden x=doğu, z=-kuzey, y=yukarı)
ORIGIN = (39.8913, 32.7790)  # (lat, lon)
DEFAULT_HEIGHT = 9.0         # yüksekliği bilinmeyen binalar için (m)
LEVEL_HEIGHT = 3.2           # kat başına metre (konut vb.)
LEVEL_HEIGHT_INST = 4.0      # kat başına metre: üniversite/okul/hastane/kamu (yüksek tavanlı)
