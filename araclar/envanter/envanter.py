# -*- coding: utf-8 -*-
"""Bir klasördeki bütün dosyaların envanterini çıkarır (SALT OKUNUR — orijinallere dokunmaz).

Kullanım:  py -3.12 envanter.py "<incelenecek klasör>" ["<çıktı klasörü>"]
Varsayılan çıktı: <Emo>\\davalar\\_ice-aktarma\\<YYYY-AA-GG>-<klasör-adı>\\

Üretilenler:
  ENVANTER.md        → özet: dosya türleri, en büyük dosyalar, veritabanı tabloları, belge önizlemeleri
  manifest.csv       → her dosya: yol, boyut, uzantı, değişiklik tarihi, SHA-256, tür, metin çıkarıldı mı
  metin/             → belgelerden çıkarılan düz metinler (UDF, DOCX, PDF, TXT, HTML, RTF, XML, JSON)
  veritabani/        → SQLite / Access tablolarının ilk satırları (CSV)
"""
import csv
import datetime as dt
import hashlib
import html
import json
import re
import sqlite3
import sys
import zipfile
from collections import Counter
from pathlib import Path

BELGE = {".udf", ".docx", ".pdf", ".txt", ".rtf", ".html", ".htm", ".xml", ".json", ".csv", ".md", ".odt"}
VERITABANI = {".db", ".sqlite", ".sqlite3", ".db3", ".mdb", ".accdb", ".sdf", ".fdb"}
TABLO = {".xlsx", ".xls", ".ods"}
GORSEL = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".heic"}
PROGRAM = {".exe", ".dll", ".msi", ".sys", ".ocx", ".pak", ".bin", ".so", ".jar", ".pyd", ".node"}
ATLA_KLASOR = {"__pycache__", ".git", "node_modules"}
MAKS_METIN = 2_000_000  # tek belgeden çıkarılacak en fazla karakter


def tur(uz):
    for ad, kume in (("belge", BELGE), ("veritabanı", VERITABANI), ("tablo", TABLO),
                     ("görsel", GORSEL), ("program", PROGRAM)):
        if uz in kume:
            return ad
    return "diğer"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def xml_metin(x):
    x = re.sub(r"<(w:p|text:p|paragraph)[ >/]", "\n<", x)
    x = re.sub(r"<[^>]+>", " ", x)
    return re.sub(r"[ \t]+", " ", html.unescape(x)).strip()


def metin_cikar(p, uz):
    try:
        if uz == ".udf":
            with zipfile.ZipFile(p) as z:
                ad = next((n for n in z.namelist() if n.lower().endswith("content.xml")), None)
                if not ad:
                    return None, "UDF içinde content.xml yok"
                x = z.read(ad).decode("utf-8", "replace")
                m = re.search(r"<!\[CDATA\[(.*?)\]\]>", x, re.S)
                return (m.group(1) if m else xml_metin(x)), None
        if uz in (".docx", ".odt"):
            with zipfile.ZipFile(p) as z:
                ad = "word/document.xml" if uz == ".docx" else "content.xml"
                return xml_metin(z.read(ad).decode("utf-8", "replace")), None
        if uz == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                return None, "pypdf yok (py -3.12 -m pip install pypdf)"
            r = PdfReader(str(p))
            t = "\n".join((s.extract_text() or "") for s in r.pages)
            return t, (None if t.strip() else "PDF'te metin katmanı yok (taranmış; OCR gerekir)")
        if uz in (".html", ".htm", ".xml", ".rtf"):
            t = p.read_text("utf-8", errors="replace")
            if uz == ".rtf":
                t = re.sub(r"\\[a-z]+-?\d* ?|[{}]", " ", t)
            return xml_metin(t) if uz != ".rtf" else t, None
        if uz in (".txt", ".md", ".csv", ".json"):
            return p.read_text("utf-8", errors="replace"), None
    except Exception as e:  # bozuk / şifreli dosya
        return None, f"okunamadı: {type(e).__name__}: {e}"
    return None, None


def sqlite_incele(p, hedef):
    satirlar = []
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        tablolar = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for t in tablolar:
            n = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            cur = con.execute(f'SELECT * FROM "{t}" LIMIT 200')
            kolon = [d[0] for d in cur.description]
            guvenli = re.sub(r"[^\w]+", "_", t)
            dosya = hedef / f"{p.stem}__{guvenli}.csv"
            with open(dosya, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(kolon)
                w.writerows(cur.fetchall())
            satirlar.append(f"| `{p.name}` | `{t}` | {n:,} | {', '.join(kolon[:12])}{' …' if len(kolon) > 12 else ''} |")
        con.close()
    except Exception as e:
        satirlar.append(f"| `{p.name}` | — | — | SQLite olarak açılamadı ({type(e).__name__}); Access/başka biçim veya şifreli olabilir |")
    return satirlar


def main():
    if len(sys.argv) < 2:
        sys.exit('Kullanım: py -3.12 envanter.py "<incelenecek klasör>" ["<çıktı klasörü>"]')
    kok = Path(sys.argv[1]).expanduser().resolve()
    if not kok.is_dir():
        sys.exit(f"Klasör bulunamadı: {kok}")
    emo = Path(__file__).resolve().parents[2]
    cikti = Path(sys.argv[2]) if len(sys.argv) > 2 else \
        emo / "davalar" / "_ice-aktarma" / f"{dt.date.today():%Y-%m-%d}-{re.sub(r'[^\w-]+', '_', kok.name)}"
    (cikti / "metin").mkdir(parents=True, exist_ok=True)
    (cikti / "veritabani").mkdir(parents=True, exist_ok=True)

    kayitlar, turler, uzantilar, db_satir, onizleme, hatalar = [], Counter(), Counter(), [], [], []
    for p in sorted(kok.rglob("*")):
        if not p.is_file() or any(k in ATLA_KLASOR for k in p.parts):
            continue
        uz = p.suffix.lower()
        st = p.stat()
        t = tur(uz)
        turler[t] += 1
        uzantilar[uz or "(uzantısız)"] += 1
        kayit = {"yol": str(p.relative_to(kok)), "boyut": st.st_size, "uzanti": uz, "tur": t,
                 "degisiklik": dt.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                 "sha256": sha256(p) if st.st_size < 2_000_000_000 else "", "metin": ""}
        if t == "belge":
            m, hata = metin_cikar(p, uz)
            if m and m.strip():
                hedef = cikti / "metin" / (re.sub(r"[^\w.-]+", "_", kayit["yol"]) + ".txt")
                hedef.write_text(m[:MAKS_METIN], encoding="utf-8")
                kayit["metin"] = hedef.name
                onizleme.append((kayit["yol"], re.sub(r"\s+", " ", m)[:300]))
            if hata:
                hatalar.append((kayit["yol"], hata))
        if t == "veritabanı":
            db_satir += sqlite_incele(p, cikti / "veritabani")
        kayitlar.append(kayit)

    with open(cikti / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(kayitlar[0].keys()) if kayitlar else ["yol"])
        w.writeheader()
        w.writerows(kayitlar)

    toplam = sum(k["boyut"] for k in kayitlar)
    md = [f"# Envanter — {kok}", "",
          f"Tarih: {dt.datetime.now():%d.%m.%Y %H:%M} · Dosya: {len(kayitlar):,} · Toplam: {toplam / 1e6:,.1f} MB",
          "", "> Salt okunur inceleme: orijinal dosyalara dokunulmadı.", "",
          "## Dosya türleri", "| Tür | Adet |", "|---|---|"]
    md += [f"| {k} | {v:,} |" for k, v in turler.most_common()]
    md += ["", "## Uzantılar (ilk 25)", "| Uzantı | Adet |", "|---|---|"]
    md += [f"| `{k}` | {v:,} |" for k, v in uzantilar.most_common(25)]
    md += ["", "## En büyük 20 dosya", "| Dosya | MB |", "|---|---|"]
    md += [f"| `{k['yol']}` | {k['boyut'] / 1e6:,.1f} |" for k in sorted(kayitlar, key=lambda x: -x["boyut"])[:20]]
    if db_satir:
        md += ["", "## Veritabanları", "| Dosya | Tablo | Satır | Sütunlar |", "|---|---|---|---|"] + db_satir
        md += ["", "Her tablonun ilk 200 satırı `veritabani/` klasöründe CSV olarak."]
    md += ["", f"## Belgeler — metni çıkarılanlar ({len(onizleme):,})", "| Dosya | İlk 300 karakter |", "|---|---|"]
    md += [f"| `{y}` | {o.replace('|', '/')} |" for y, o in onizleme[:300]]
    if len(onizleme) > 300:
        md.append(f"| … | ve {len(onizleme) - 300:,} belge daha (manifest.csv) |")
    if hatalar:
        md += ["", f"## Okunamayan / sorunlu belgeler ({len(hatalar):,})", "| Dosya | Sebep |", "|---|---|"]
        md += [f"| `{y}` | {h} |" for y, h in hatalar[:200]]
    (cikti / "ENVANTER.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Bitti: {len(kayitlar):,} dosya · {toplam / 1e6:,.1f} MB → {cikti}")
    print(json.dumps(dict(turler), ensure_ascii=False))


if __name__ == "__main__":
    main()
