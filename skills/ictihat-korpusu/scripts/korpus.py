#!/usr/bin/env python3
"""Türk İçtihat Korpusu (11 milyon karar) — künye doğrulama ve metin arama.

Kaynak veri: Hugging Face `iaiauu/ictihatlar` (Hamza Bağırsakçı, 2026, CC0-1.0).
Yargıtay 1997–2026 · Danıştay · UYAP Emsal (BAM/ilk derece) 2017–2026 · AYM norm · AYM bireysel başvuru.
Fikir: karti.av.tr "İçtihat arama aracı"; bu sürüm HTTPS + SHA-256 doğrulamalı indirme ve
ajan dostu (--json) çıktı ekler.

KOMUTLAR
  korpus.py indir                          # ≈5,5 GB; her dosya SHA-256 ile doğrulanır
  korpus.py indeks                         # künye indeksi (birkaç dakika)
  korpus.py durum
  korpus.py kunye --esas 2016/57111 [--karar 2023/6863] [--daire "1. Hukuk"] [--kaynak yargitay]
  korpus.py ara "muris muvazaası" "tapu iptal" [--veya] [--kaynak yargitay] [--daire "1. Hukuk"] [--yil 2015-]
  korpus.py oku <id>   |   korpus.py oku --esas 2022/2530 --karar 2022/4045 [--daire "9. Hukuk"]

Korpus dizini: --korpus, yoksa $EMO_KORPUS, yoksa ~/.emo/korpus
Arama Türkçe harf katlamalıdır (ı/i, ş/s, ğ/g, ç/c, ü/u, ö/o, â/a eşdeğer).
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = "iaiauu/ictihatlar"
SURUM = "ec10fcae321fd32fd597d15190a798baac087797"  # sabitlenmiş veri seti sürümü
API = f"https://huggingface.co/api/datasets/{REPO}/tree/{SURUM}/data"
RAW = f"https://huggingface.co/datasets/{REPO}/resolve/{SURUM}/"

KAYNAKLAR = {
    "yargitay": "Yargıtay",
    "danistay": "Danıştay",
    "emsal": "UYAP Emsal",
    "aym_norm": "AYM Norm Denetimi",
    "aym_bb": "AYM Bireysel Başvuru",
}
SUTUNLAR = "id, source, document_id, court, esas_no, karar_no, karar_tarihi, year, text_len"


def korpus_dizini(arg):
    return Path(arg or os.environ.get("EMO_KORPUS") or Path.home() / ".emo" / "korpus").expanduser()


# ---------------------------------------------------------------- Türkçe harf katlama
_ESLER = ["iıİI", "sşSŞ", "gğGĞ", "cçCÇ", "uüUÜ", "oöOÖ", "aâAÂ"]
_HARITA = {ch: grup for grup in _ESLER for ch in grup}


def desen(terim):
    """Türkçe harf katlamalı, boşluğa toleranslı RE2 deseni."""
    p = []
    for ch in terim:
        if ch.isspace():
            p.append(r"\s+")
        elif ch in _HARITA:
            p.append("[" + _HARITA[ch] + "]")
        elif ch.isalpha():
            p.append("[" + ch.lower() + ch.upper() + "]")
        else:
            p.append(re.escape(ch))
    return "".join(p)


def daire_deseni(daire):
    """'1. Hukuk' yazıldığında 11. veya 21. Hukuk Dairesi eşleşmesin."""
    d = desen(daire.strip())
    return ("(^|[^0-9])" + d) if daire.strip()[:1].isdigit() else d


# ---------------------------------------------------------------- indirme
def _json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def dosya_listesi():
    dosyalar = []
    for kaynak in KAYNAKLAR:
        for x in _json(f"{API}/{kaynak}"):
            if x["path"].endswith(".parquet"):
                dosyalar.append((x["path"], x["lfs"]["oid"], x["lfs"]["size"]))
    return dosyalar


def sha256(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(1 << 22), b""):
            h.update(blok)
    return h.hexdigest()


def indir_dosya(yol, hedef, beklenen, boyut, deneme=5):
    tamam = hedef.with_suffix(".parquet.ok")
    if tamam.exists() and hedef.exists() and hedef.stat().st_size == boyut:
        return "zaten var"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_suffix(".parquet.part")
    for i in range(deneme):
        try:
            bas = gecici.stat().st_size if gecici.exists() else 0
            istek = urllib.request.Request(RAW + yol, headers={"Range": f"bytes={bas}-"} if bas else {})
            with urllib.request.urlopen(istek, timeout=120) as r, open(gecici, "ab" if bas else "wb") as f:
                if bas and r.status != 206:  # sunucu kaldığı yerden vermedi
                    f.truncate(0)
                while blok := r.read(1 << 22):
                    f.write(blok)
            break
        except Exception as e:
            print(f"  ! {yol}: {e} — tekrar ({i + 1}/{deneme})", file=sys.stderr)
            time.sleep(2 ** (i + 1))
    else:
        raise SystemExit(f"İndirilemedi: {yol}")
    gercek = sha256(gecici)
    if gercek != beklenen:
        gecici.unlink()
        raise SystemExit(f"SHA-256 UYUŞMAZLIĞI: {yol}\n beklenen {beklenen}\n gelen    {gercek}\nDosya silindi.")
    gecici.rename(hedef)
    tamam.write_text(beklenen)
    return "indirildi ✓ sha256"


def cmd_indir(a):
    kok = korpus_dizini(a.korpus)
    dosyalar = dosya_listesi()
    toplam = sum(b for _, _, b in dosyalar)
    print(f"{len(dosyalar)} dosya · {toplam / 1e9:.2f} GB · sürüm {SURUM[:10]} → {kok}")
    for yol, oid, boyut in dosyalar:
        durum = indir_dosya(yol, kok / yol, oid, boyut)
        print(f"  {yol}  {boyut / 1e6:,.0f} MB  {durum}")
    (kok / "surum.json").write_text(json.dumps({"repo": REPO, "surum": SURUM, "lisans": "CC0-1.0",
                                                "dosya": len(dosyalar), "bayt": toplam}, indent=1))
    print("Tamam. Sıradaki adım: korpus.py indeks")


# ---------------------------------------------------------------- sorgu altyapısı
def duck():
    try:
        import duckdb
    except ImportError:
        raise SystemExit("duckdb gerekli: pip install -r requirements.txt")
    return duckdb


def parquet(kok, kaynak=None):
    kaynaklar = kaynak or list(KAYNAKLAR)
    bilinmeyen = [k for k in kaynaklar if k not in KAYNAKLAR]
    if bilinmeyen:
        raise SystemExit("Bilinmeyen kaynak: " + ", ".join(bilinmeyen) + " · geçerli: " + ", ".join(KAYNAKLAR))
    yollar = [str(kok / "data" / k / "*.parquet").replace("\\", "/") for k in kaynaklar
              if list((kok / "data" / k).glob("*.parquet"))]
    if not yollar:
        raise SystemExit(f"Korpus bulunamadı: {kok}\nKurulum: korpus.py indir && korpus.py indeks")
    return "read_parquet([" + ",".join("'" + y + "'" for y in yollar) + "])"


def kosullar(a):
    k, p = [], []
    if getattr(a, "kaynak", None):
        k.append("source IN (" + ",".join("?" * len(a.kaynak)) + ")")
        p += a.kaynak
    if getattr(a, "daire", None):
        k.append("regexp_matches(coalesce(court,''), ?)")
        p.append(daire_deseni(a.daire))
    if getattr(a, "yil", None):
        m = re.fullmatch(r"(\d{4})?\s*-\s*(\d{4})?|(\d{4})", a.yil.strip())
        if not m:
            raise SystemExit("--yil biçimi: 2019 · 2015-2026 · 2015- · -2010")
        if m.group(3):
            k.append("year = ?"); p.append(int(m.group(3)))
        else:
            if m.group(1):
                k.append("year >= ?"); p.append(int(m.group(1)))
            if m.group(2):
                k.append("year <= ?"); p.append(int(m.group(2)))
    if getattr(a, "esas", None):
        k.append("esas_no = ?"); p.append(a.esas.strip())
    if getattr(a, "karar", None):
        k.append("karar_no = ?"); p.append(a.karar.strip())
    return k, p


def where(k):
    return (" WHERE " + " AND ".join(k)) if k else ""


def kunye_satiri(r):
    return (f"{KAYNAKLAR.get(r['source'], r['source'])} · {r['court'] or '-'} · "
            f"E. {r['esas_no'] or '-'} · K. {r['karar_no'] or '-'} · T. {r['karar_tarihi'] or '-'}")


def cikti(satirlar, a, baslik=None):
    if a.json:
        print(json.dumps(satirlar, ensure_ascii=False, indent=1, default=str))
        return
    if baslik:
        print(baslik)
    for i, r in enumerate(satirlar, 1):
        print(f"\n[{i}] {kunye_satiri(r)}")
        print(f"    id: {r['id']} · {r.get('text_len') or 0:,} karakter".replace(",", "."))
        if r.get("baglam"):
            print("    > " + re.sub(r"\s+", " ", r["baglam"]).strip())
        if r.get("text"):
            print("\n" + r["text"])


# ---------------------------------------------------------------- komutlar
def cmd_indeks(a):
    kok = korpus_dizini(a.korpus)
    hedef = kok / "kunye.duckdb"
    if hedef.exists():
        hedef.unlink()
    con = duck().connect(str(hedef))
    print("Künye indeksi kuruluyor (metin hariç)…")
    con.sql(f"CREATE TABLE kunye AS SELECT {SUTUNLAR}, raw_sha256 FROM {parquet(kok)}")
    con.sql("CREATE INDEX ix_esas ON kunye(esas_no)")
    con.sql("CREATE INDEX ix_karar ON kunye(karar_no)")
    n = con.sql("SELECT count(*) FROM kunye").fetchone()[0]
    con.close()
    print(f"Bitti: {n:,} künye · {hedef.stat().st_size / 1e6:,.0f} MB".replace(",", "."))


def cmd_durum(a):
    kok = korpus_dizini(a.korpus)
    print("Korpus:", kok)
    for k, ad in KAYNAKLAR.items():
        f = list((kok / "data" / k).glob("*.parquet"))
        ok = len(list((kok / "data" / k).glob("*.parquet.ok")))
        print(f"  {ad:<22} {len(f):>3} dosya ({ok} doğrulandı) {sum(x.stat().st_size for x in f) / 1e9:6.2f} GB")
    print("  Künye indeksi:", "var" if (kok / "kunye.duckdb").exists() else "YOK (korpus.py indeks)")


def cmd_kunye(a):
    if not (a.esas or a.karar):
        raise SystemExit("En az --esas veya --karar verin (biçim: 2019/4215).")
    kok = korpus_dizini(a.korpus)
    k, p = kosullar(a)
    if (kok / "kunye.duckdb").exists():
        con, tablo = duck().connect(str(kok / "kunye.duckdb"), read_only=True), "kunye"
    else:
        con, tablo = duck().connect(), parquet(kok, a.kaynak)
    rows = con.execute(f"SELECT {SUTUNLAR} FROM {tablo}{where(k)} ORDER BY karar_tarihi DESC LIMIT 200", p)
    satirlar = [dict(zip([d[0] for d in rows.description], r)) for r in rows.fetchall()]
    if not satirlar and not a.json:
        print("KAYIT BULUNAMADI — bu künyeyle korpusta karar yok.")
        print("Olası nedenler: künye yanlış/uydurma · daire adı farklı (--daire olmadan dene) · kapsam dışı.")
        print("Kesin sonuç resmî kaynaktan (Mütalaa karar_ara) alınır.")
        return
    cikti(satirlar, a, f"{len(satirlar)} kayıt")


def cmd_ara(a):
    kok = korpus_dizini(a.korpus)
    k, p = kosullar(a)
    desenler = [desen(t) for t in a.terim]
    k.append("(" + (" OR " if a.veya else " AND ").join(["regexp_matches(text, ?)"] * len(desenler)) + ")")
    p += desenler
    ctx = "(?s).{0," + str(a.baglam) + "}(?:" + desenler[0] + ").{0," + str(a.baglam) + "}"
    sira = {"yeni": "karar_tarihi DESC", "eski": "karar_tarihi ASC", "uzun": "text_len DESC"}[a.sira]
    con = duck().connect()
    con.execute(f"CREATE TEMP TABLE h AS SELECT {SUTUNLAR}, regexp_extract(text, ?) AS baglam "
                f"FROM {parquet(kok, a.kaynak)}{where(k)}", [ctx] + p)
    toplam = con.sql("SELECT count(*) FROM h").fetchone()[0]
    rows = con.sql(f"SELECT * FROM h ORDER BY {sira} NULLS LAST LIMIT {int(a.limit)}")
    satirlar = [dict(zip([d[0] for d in rows.description], r)) for r in rows.fetchall()]
    cikti(satirlar, a, f"{toplam:,} karar eşleşti (ilk {len(satirlar)}, sıra: {a.sira})".replace(",", "."))


def cmd_oku(a):
    kok = korpus_dizini(a.korpus)
    if a.id:
        k, p = ["id = ?"], [a.id]
    else:
        k, p = kosullar(a)
        if not (a.esas or a.karar):
            raise SystemExit("<id> ya da --esas / --karar verin.")
    con = duck().connect()
    rows = con.execute(f"SELECT {SUTUNLAR}, text FROM {parquet(kok, a.kaynak)}{where(k)} "
                       f"ORDER BY text_len DESC LIMIT {int(a.limit)}", p)
    satirlar = [dict(zip([d[0] for d in rows.description], r)) for r in rows.fetchall()]
    if not satirlar:
        raise SystemExit("Kayıt bulunamadı.")
    cikti(satirlar, a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--korpus")
    ap.add_argument("--json", action="store_true")
    alt = ap.add_subparsers(dest="komut", required=True)

    def ortak(s):
        s.add_argument("--kaynak", nargs="+", metavar="K", help=" ".join(KAYNAKLAR))
        s.add_argument("--daire", help='ör. "1. Hukuk", "Hukuk Genel", "12. Ceza"')
        s.add_argument("--yil", help="2019 · 2015-2026 · 2015- · -2010")

    alt.add_parser("indir").set_defaults(f=cmd_indir)
    alt.add_parser("indeks").set_defaults(f=cmd_indeks)
    alt.add_parser("durum").set_defaults(f=cmd_durum)

    s = alt.add_parser("kunye"); s.add_argument("--esas"); s.add_argument("--karar"); ortak(s)
    s.set_defaults(f=cmd_kunye)

    s = alt.add_parser("ara"); s.add_argument("terim", nargs="+")
    s.add_argument("--veya", action="store_true"); s.add_argument("--limit", type=int, default=15)
    s.add_argument("--baglam", type=int, default=250)
    s.add_argument("--sira", choices=["yeni", "eski", "uzun"], default="yeni"); ortak(s)
    s.set_defaults(f=cmd_ara)

    s = alt.add_parser("oku"); s.add_argument("id", nargs="?"); s.add_argument("--esas"); s.add_argument("--karar")
    s.add_argument("--limit", type=int, default=1); ortak(s)
    s.set_defaults(f=cmd_oku)

    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
