#!/usr/bin/env python3
"""Emo içtihat arşivini kurar.

Kaynak: Hugging Face veri seti `muhamparlak/turkish-law-bge-m3-embeddings` (CC-BY-4.0).
  - emsal_kararlar: ~702 bin parça, Yargıtay + Danıştay kararları (BAAI/bge-m3, 1024 boyut)
  - mevzuat: 8 temel kanun (Anayasa, TMK, TBK, TTK, TCK, CMK, HMK, İşK)

Ham parquet dosyalarını indirir, sonra iki küme için şunları üretir:
  <arsiv>/<kume>_meta.parquet   → vektörsüz metin + künye + daire + yıl
  <arsiv>/<kume>_vec.f16        → normalize edilmiş float16 vektörler (satır sırası meta ile aynı)
  <arsiv>/bilgi.json            → kurulum bilgisi

Arşiv dizini: --arsiv, yoksa $EMO_ARSIV, yoksa ~/.emo/arsiv
Kullanım:  python3 indir.py [--kume emsal|mevzuat|hepsi] [--ham-sakla]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

REPO = "muhamparlak/turkish-law-bge-m3-embeddings"
API = f"https://huggingface.co/api/datasets/{REPO}"
RAW = f"https://huggingface.co/datasets/{REPO}/resolve/main/"
KLASOR = {"emsal": "emsal_kararlar/", "mevzuat": "mevzuat/"}


def arsiv_dizini(arg):
    return Path(arg or os.environ.get("EMO_ARSIV") or Path.home() / ".emo" / "arsiv").expanduser()


def indir(url, hedef, deneme=4):
    if hedef.exists() and hedef.stat().st_size > 0:
        return
    gecici = hedef.with_suffix(hedef.suffix + ".part")
    for i in range(deneme):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(gecici, "wb") as f:
                while True:
                    blok = r.read(1 << 20)
                    if not blok:
                        break
                    f.write(blok)
            gecici.rename(hedef)
            return
        except Exception as e:  # ağ hatasında tekrar dene
            bekle = 2 ** (i + 1)
            print(f"  ! {hedef.name}: {e} — {bekle} sn sonra tekrar", file=sys.stderr)
            time.sleep(bekle)
    raise SystemExit(f"İndirilemedi: {url}")


DAIRE_RE = re.compile(r"^\**\s*(.*?)\s{2,}")


def daire_cikar(metin):
    ilk = metin.lstrip()[:200]
    m = DAIRE_RE.match(ilk)
    return (m.group(1) if m else ilk.split("\n", 1)[0]).strip("* ").strip()


def yil_cikar(tarih):
    m = re.search(r"(\d{4})\s*$", tarih or "")
    return int(m.group(1)) if m else 0


def isle(kume, ham_dosyalar, arsiv):
    vec_yol = arsiv / f"{kume}_vec.f16"
    meta_yol = arsiv / f"{kume}_meta.parquet"
    yazici = None
    toplam = 0
    with open(vec_yol, "wb") as vf:
        for yol in ham_dosyalar:
            t = pq.read_table(yol)
            liste = t.column("vector").combine_chunks()
            v = liste.flatten().to_numpy(zero_copy_only=False).astype(np.float32).reshape(len(t), -1)
            v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
            vf.write(v.astype(np.float16).tobytes())
            meta = t.drop(["vector"])
            if kume == "emsal":
                metinler = meta.column("text").to_pylist()
                meta = meta.append_column("daire", pa.array([daire_cikar(x) for x in metinler]))
                meta = meta.append_column("yil", pa.array([yil_cikar(x) for x in meta.column("tarih").to_pylist()], pa.int16()))
            if yazici is None:
                yazici = pq.ParquetWriter(meta_yol, meta.schema, compression="zstd")
            yazici.write_table(meta.cast(yazici.schema))
            toplam += len(v)
            print(f"  ✓ {yol.name}: {len(v)} satır (toplam {toplam})")
    if yazici:
        yazici.close()
    return toplam


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arsiv")
    ap.add_argument("--kume", choices=["emsal", "mevzuat", "hepsi"], default="hepsi")
    ap.add_argument("--ham-sakla", action="store_true", help="Ham parquet dosyalarını silme")
    a = ap.parse_args()

    arsiv = arsiv_dizini(a.arsiv)
    ham = arsiv / "ham"
    ham.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(API, timeout=60) as r:
        bilgi = json.load(r)
    dosyalar = [s["rfilename"] for s in bilgi["siblings"] if s["rfilename"].endswith(".parquet")]

    kumeler = ["emsal", "mevzuat"] if a.kume == "hepsi" else [a.kume]
    ozet = {"kaynak": REPO, "surum": bilgi.get("sha"), "lisans": "CC-BY-4.0", "kurulum": date.today().isoformat(), "kumeler": {}}
    bilgi_yol = arsiv / "bilgi.json"
    if bilgi_yol.exists():
        ozet["kumeler"] = json.loads(bilgi_yol.read_text()).get("kumeler", {})

    for kume in kumeler:
        secili = sorted(f for f in dosyalar if f.startswith(KLASOR[kume]))
        print(f"[{kume}] {len(secili)} dosya indiriliyor → {ham}")
        yollar = []
        for f in secili:
            hedef = ham / Path(f).name
            indir(RAW + f, hedef)
            yollar.append(hedef)
        print(f"[{kume}] işleniyor")
        ozet["kumeler"][kume] = {"satir": isle(kume, yollar, arsiv), "boyut": 1024}
        if not a.ham_sakla:
            for y in yollar:
                y.unlink()

    bilgi_yol.write_text(json.dumps(ozet, ensure_ascii=False, indent=2))
    print(f"Tamam. Arşiv: {arsiv}")


if __name__ == "__main__":
    main()
