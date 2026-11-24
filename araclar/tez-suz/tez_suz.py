# -*- coding: utf-8 -*-
"""YÖK tez özetleri veri setinden (umutertugrul/turkish-academic-theses-dataset, CC-BY-4.0)
hukuk tezlerini ayıklar ve alanlarına göre etiketler.

Kullanım:  py tez_suz.py [tezler.parquet yolu]
Varsayılan giriş: İndirilenler\\tezler.parquet
Çıktı (girişle aynı klasöre): hukuk_tezleri.parquet  +  hukuk_tezleri_ozet.txt
"""
import os
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    sys.exit("duckdb bulunamadı. Önce:  py -m pip install duckdb")

giris = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "tezler.parquet"
if not giris.exists():
    alt = Path.home() / "İndirilenler" / "tezler.parquet"
    giris = alt if alt.exists() else giris
if not giris.exists():
    sys.exit(f"Dosya bulunamadı: {giris}\nKullanım: py tez_suz.py C:\\yol\\tezler.parquet")

cikis = giris.with_name("hukuk_tezleri.parquet")
ozet = giris.with_name("hukuk_tezleri_ozet.txt")
g = str(giris).replace("\\", "/")
c = str(cikis).replace("\\", "/")

con = duckdb.connect()
sutunlar = [r[0] for r in con.sql(f"DESCRIBE SELECT * FROM read_parquet('{g}')").fetchall()]
gerekli = {"tez_no", "title_tr", "subject", "location", "abstract_tr"}
eksik = gerekli - set(sutunlar)
if eksik:
    sys.exit(f"Beklenen sütunlar yok: {sorted(eksik)}\nDosyadaki sütunlar: {sutunlar}")

def s(ad):
    return f"coalesce(CAST({ad} AS VARCHAR), '')" if ad in sutunlar else "''"

def tr_lower(ifade):
    """Türkçe küçük harf: İ→i, I→ı (standart lower() 'İ'yi bozuk çevirir)."""
    return f"lower(replace(replace({ifade}, 'İ', 'i'), 'I', 'ı'))"

metin = tr_lower(f"{s('title_tr')} || ' ' || {s('title_en')} || ' ' || {s('index')} || ' ' || {s('abstract_tr')}")
konu = tr_lower(f"{s('subject')} || ' ' || {s('location')}")

# Hukuk tezi: konu alanı veya kurum yolu hukuk içeriyor
hukuk = f"(regexp_matches({konu}, 'hukuk|\\blaw\\b|kamu hukuku|özel hukuk|ceza ve ceza muhakemesi'))"

ALANLAR = {
    "is_hukuku": r"iş hukuku|işçi|işveren|kıdem tazminat|ihbar tazminat|işe iade|fazla çalışma|sendika|toplu iş|iş sözleşme|sosyal güvenlik|iş kazası|mobbing",
    "ceza": r"ceza|suç|kovuşturma|soruşturma|tutuklama|sanık|müdafi|cmk|tck|delil yasağı|hükmün açıklanmasının geri|uzlaştırma|infaz",
    "aile": r"boşanma|nafaka|velayet|mal rejimi|edinilmiş mal|katılma alacağı|aile hukuku|evlilik|nişan|aile konutu|6284|kadına karşı şiddet",
    "esya_tapu": r"tapu|taşınmaz|mülkiyet|eşya hukuku|ortaklığın giderilmesi|el atma|elatma|ecrimisil|tescil|kat mülkiyeti|zilyetlik|ipotek|sicil",
    "miras": r"miras|tenkis|muris|muvazaa|vasiyet|tereke|saklı pay|mirasçı|ölüme bağlı",
    "vesayet_kisiler": r"vesayet|vasi|kısıtl|fiil ehliyeti|ayırt etme gücü|yasal danışman|kayyım|engelli|akıl hastalığı",
    "usul": r"medeni usul|hukuk muhakemeleri|ispat|delil|istinaf|temyiz|bilirkişi|ihtiyati tedbir|ihtiyati haciz|arabuluculuk|icra|iflas",
    "borclar": r"borçlar hukuku|sözleşme|haksız fiil|tazminat|sebepsiz zenginleşme|kira",
}
etiketler = ", ".join(f"regexp_matches({metin}, '{p}') AS {a}" for a, p in ALANLAR.items())
secili = ", ".join(x for x in ["tez_no", "pdf_url", "title_tr", "title_en", "author", "advisor", "location",
                               "subject", "index", "status", "degree", "language", "year", "pages",
                               "abstract_tr", "abstract_en"] if x in sutunlar)

print(f"Okunuyor: {giris}")
toplam = con.sql(f"SELECT count(*) FROM read_parquet('{g}')").fetchone()[0]
con.sql(f"""COPY (SELECT {secili}, {etiketler} FROM read_parquet('{g}') WHERE {hukuk})
            TO '{c}' (FORMAT parquet, COMPRESSION zstd)""")

satirlar = [f"Giriş: {giris}", f"Toplam tez: {toplam:,}"]
n = con.sql(f"SELECT count(*) FROM read_parquet('{c}')").fetchone()[0]
satirlar.append(f"Hukuk tezi: {n:,}")
for a in ALANLAR:
    k = con.sql(f"SELECT count(*) FROM read_parquet('{c}') WHERE {a}").fetchone()[0]
    satirlar.append(f"  {a:<16} {k:,}")
if "degree" in sutunlar:
    for d, k in con.sql(f"SELECT degree, count(*) FROM read_parquet('{c}') GROUP BY 1 ORDER BY 2 DESC LIMIT 5").fetchall():
        satirlar.append(f"  derece: {d} — {k:,}")
satirlar.append(f"Çıktı: {cikis} ({os.path.getsize(cikis) / 1e6:.1f} MB)")
ozet.write_text("\n".join(satirlar), encoding="utf-8")
print("\n".join(satirlar))
print("\nBitti. hukuk_tezleri.parquet dosyasını Claude'a yükleyin.")
