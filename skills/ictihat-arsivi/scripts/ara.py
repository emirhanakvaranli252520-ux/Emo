#!/usr/bin/env python3
"""Emo içtihat arşivinde arama.

Modlar:
  Anlamsal arama:   ara.py "işe iade geçerli fesih performans düşüklüğü savunma alınmaması"
  Esas no ile:      ara.py --esas 2015/1234 [--daire "9. Hukuk"]
  Metin içinde:     ara.py --metin "muris muvazaası" --daire "1. Hukuk" --yil-min 2018
  Tam karar metni:  ara.py --tam <doc_id>
  Kanun maddesi:    ara.py --kume mevzuat --madde "TMK 6"
  Mevzuatta anlam:  ara.py --kume mevzuat "boşanmada mal rejiminin tasfiyesi katılma alacağı"

Süzgeçler: --kaynak Yargıtay|Danıştay  --daire "<metin parçası>"  --yil-min  --yil-max  -k
Çıktı: Markdown (varsayılan) veya --json.

Arşiv dizini: --arsiv, yoksa $EMO_ARSIV, yoksa ~/.emo/arsiv (kurulum: indir.py)
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq

BOYUT = 1024
MODEL = "BAAI/bge-m3"
# Kurumsal/proxy ağlarda Xet aktarımı engellenebiliyor; klasik indirme her yerde çalışır.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


def arsiv_dizini(arg):
    return Path(arg or os.environ.get("EMO_ARSIV") or Path.home() / ".emo" / "arsiv").expanduser()


def kume_yukle(arsiv, kume, sutunlar=None):
    meta_yol = arsiv / f"{kume}_meta.parquet"
    if not meta_yol.exists():
        raise SystemExit(f"Arşiv bulunamadı: {meta_yol}\nKurulum: python3 scripts/arsiv/indir.py")
    return pq.read_table(meta_yol, columns=sutunlar)


def satir_getir(arsiv, kume, indeksler):
    """Seçilen satırları yalnızca ilgili row group'lardan okur (bellek dostu)."""
    pf = pq.ParquetFile(arsiv / f"{kume}_meta.parquet")
    sinirlar, bas = [], 0
    for g in range(pf.num_row_groups):
        n = pf.metadata.row_group(g).num_rows
        sinirlar.append((bas, bas + n))
        bas += n
    onbellek, sonuc = {}, []
    for i in indeksler:
        g = next(j for j, (b, s) in enumerate(sinirlar) if b <= i < s)
        if g not in onbellek:
            onbellek[g] = pf.read_row_group(g)
        sonuc.append(onbellek[g].slice(i - sinirlar[g][0], 1).to_pylist()[0])
    return sonuc


def vektorler(arsiv, kume, n):
    return np.memmap(arsiv / f"{kume}_vec.f16", dtype=np.float16, mode="r", shape=(n, BOYUT))


def sorgu_vektoru(sorgu):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit("Anlamsal arama için: pip install sentence-transformers  (veya --esas / --metin modlarını kullan)")
    model = SentenceTransformer(MODEL, device="cpu")
    return model.encode([sorgu], normalize_embeddings=True)[0].astype(np.float32)


def sade(metin, n=None):
    metin = re.sub(r"\s+", " ", metin or "").strip()
    return metin if n is None or len(metin) <= n else metin[:n].rsplit(" ", 1)[0] + " …"


def kunye(r):
    daire = r.get("daire") or ""
    on = "" if daire.startswith(r.get("kaynak", "")) else f"{r.get('kaynak', '')} "
    return f"{on}{daire}, E. {r.get('esas_no')}, K. {r.get('karar_no')}, T. {r.get('tarih')}"


def suzgec(meta, a):
    maske = None

    def ve(m):
        nonlocal maske
        maske = m if maske is None else pc.and_(maske, m)

    if a.kaynak:
        ve(pc.equal(meta["kaynak"], a.kaynak))
    if a.daire:
        ve(pc.match_substring(meta["daire"], a.daire, ignore_case=True))
    if a.yil_min:
        ve(pc.greater_equal(meta["yil"], a.yil_min))
    if a.yil_max:
        ve(pc.less_equal(meta["yil"], a.yil_max))
    return None if maske is None else np.asarray(maske.to_numpy(zero_copy_only=False), dtype=bool)


def anlamsal(arsiv, kume, sorgu, a):
    sutunlar = ["doc_id", "kaynak", "daire", "yil"] if kume == "emsal" else ["id"]
    meta = kume_yukle(arsiv, kume, sutunlar)
    n = len(meta)
    V = vektorler(arsiv, kume, n)
    q = sorgu_vektoru(sorgu)
    maske = suzgec(meta, a) if kume == "emsal" else None

    skor = np.empty(n, dtype=np.float32)
    blok = 65536
    for i in range(0, n, blok):
        skor[i:i + blok] = V[i:i + blok].astype(np.float32) @ q
    if maske is not None:
        skor[~maske] = -np.inf

    aday = np.argpartition(-skor, min(a.k * 20, n - 1))[: a.k * 20]
    aday = aday[np.argsort(-skor[aday])]
    aday = aday[np.isfinite(skor[aday])]

    if kume == "emsal":
        doc = meta.column("doc_id").to_numpy(zero_copy_only=False)
        secilen, gorulen = [], set()
        for i in aday:
            if doc[i] not in gorulen:
                gorulen.add(doc[i])
                secilen.append(int(i))
            if len(secilen) == a.k:
                break
    else:
        secilen = [int(i) for i in aday[: a.k]]

    tam = satir_getir(arsiv, kume, secilen)
    for r, i in zip(tam, secilen):
        r["skor"] = round(float(skor[i]), 4)
    return tam


def tam_metin(arsiv, doc_id):
    meta = kume_yukle(arsiv, "emsal")
    parcalar = meta.filter(pc.equal(meta["doc_id"], doc_id)).sort_by("chunk_idx").to_pylist()
    if not parcalar:
        raise SystemExit(f"Belge bulunamadı: {doc_id}")
    metin = parcalar[0]["text"]
    for p in parcalar[1:]:
        sonraki = p["text"]
        ortak = 0
        for u in range(min(700, len(metin), len(sonraki)), 20, -1):
            if metin.endswith(sonraki[:u]):
                ortak = u
                break
        metin += sonraki[ortak:] if ortak else "\n" + sonraki
    r = dict(parcalar[0])
    r["text"] = metin
    return r


def esas_ara(arsiv, a):
    meta = kume_yukle(arsiv, "emsal")
    m = pc.or_(pc.equal(meta["esas_no"], a.esas), pc.equal(meta["karar_no"], a.esas))
    sonuc = meta.filter(m)
    ek = suzgec(sonuc, a)
    if ek is not None:
        sonuc = sonuc.filter(ek)
    return tekille(sorted(sonuc.to_pylist(), key=lambda r: r["chunk_idx"]))[: a.k]


def tekille(satirlar):
    gorulen, tekil = set(), []
    for r in satirlar:
        if r["doc_id"] not in gorulen:
            gorulen.add(r["doc_id"])
            tekil.append(r)
    return tekil


def metin_ara(arsiv, a):
    meta = kume_yukle(arsiv, "emsal")
    ek = suzgec(meta, a)
    if ek is not None:
        meta = meta.filter(ek)
    sonuc = meta.filter(pc.match_substring(meta["text"], a.metin, ignore_case=True)).to_pylist()
    tekil = tekille(sonuc)
    tekil.sort(key=lambda r: r.get("yil") or 0, reverse=True)
    for r in tekil:
        r["_vurgu"] = a.metin
    return tekil[: a.k]


def pencere(metin, ifade, n):
    """Eşleşmenin çevresindeki pasajı döndürür."""
    sade_metin = sade(metin)
    i = sade_metin.casefold().find(ifade.casefold())
    if i < 0:
        return sade(sade_metin, n)
    bas = max(0, i - n // 3)
    parca = sade_metin[bas: bas + n]
    return ("… " if bas else "") + parca + (" …" if bas + n < len(sade_metin) else "")


def madde_bul(arsiv, ifade):
    m = re.match(r"\s*(\S+)\s+(?:m\.?\s*|madde\s*)?(.+?)\s*$", ifade, re.I)
    if not m:
        raise SystemExit('Biçim: --madde "TMK 6"  veya  "İşK Geçici Madde 1"')
    kisa, no = m.group(1), m.group(2)
    meta = kume_yukle(arsiv, "mevzuat")
    hedef = no if re.match(r"(geçici|ek)\s", no, re.I) else f"Madde {no}"
    sonuc = meta.filter(pc.and_(pc.equal(pc.utf8_lower(meta["kanun_kisa_ad"]), kisa.lower()),
                                pc.equal(pc.utf8_lower(meta["madde_no"]), hedef.lower())))
    return sonuc.to_pylist()


def yazdir(sonuclar, kume, a, tam=False):
    for r in sonuclar:
        r.pop("vector", None)
        if a.json and r.get("_vurgu") and not tam:
            r["text"] = pencere(r["text"], r.pop("_vurgu"), a.uzunluk)
    if a.json:
        print(json.dumps(sonuclar, ensure_ascii=False, indent=1))
        return
    if not sonuclar:
        print("Sonuç yok.")
        return
    for j, r in enumerate(sonuclar, 1):
        skor = f" · benzerlik {r['skor']}" if "skor" in r else ""
        if kume == "mevzuat":
            print(f"### {j}. {r['kanun_adi']} ({r['kanun_kisa_ad']}) {r['madde_no']}{skor}")
            print(f"`{r['id']}` · arşiv metni — yürürlük güncelliği Soorgla ile teyit edilmeli\n")
            print(r["orijinal_metin"].strip() + "\n")
        else:
            print(f"### {j}. {kunye(r)}{skor}")
            print(f"`doc_id: {r['doc_id']}` · kaynak: içtihat arşivi\n")
            if tam:
                print(r["text"].strip() + "\n")
            elif r.get("_vurgu"):
                print("> " + pencere(r["text"], r["_vurgu"], a.uzunluk) + "\n")
            else:
                print("> " + sade(r["text"], a.uzunluk) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sorgu", nargs="?")
    ap.add_argument("--arsiv")
    ap.add_argument("--kume", choices=["emsal", "mevzuat"], default="emsal")
    ap.add_argument("-k", type=int, default=8)
    ap.add_argument("--kaynak", choices=["Yargıtay", "Danıştay"])
    ap.add_argument("--daire")
    ap.add_argument("--yil-min", type=int)
    ap.add_argument("--yil-max", type=int)
    ap.add_argument("--esas", help="Esas veya karar no (ör. 2015/1234)")
    ap.add_argument("--metin", help="Karar metninde geçen ifade")
    ap.add_argument("--tam", metavar="DOC_ID", help="Kararın tam metni")
    ap.add_argument("--madde", help='Kanun maddesi (ör. "TMK 6")')
    ap.add_argument("--uzunluk", type=int, default=700, help="Özet uzunluğu (karakter)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    arsiv = arsiv_dizini(a.arsiv)

    if a.tam:
        yazdir([tam_metin(arsiv, a.tam)], "emsal", a, tam=True)
    elif a.madde:
        yazdir(madde_bul(arsiv, a.madde), "mevzuat", a)
    elif a.esas:
        yazdir(esas_ara(arsiv, a), "emsal", a)
    elif a.metin:
        yazdir(metin_ara(arsiv, a), "emsal", a)
    elif a.sorgu:
        yazdir(anlamsal(arsiv, a.kume, a.sorgu, a), a.kume, a)
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
