# -*- coding: utf-8 -*-
"""Bütün dava klasörlerindeki süreleri ve durumları tek tabloda toplar.

Kullanım:  py -3.12 portfoy.py [davalar klasörü] [--gun 30] [--json]
Okur: davalar/*/dava.md (künye tablosu) ve davalar/*/sureler.md (süre tablosu; "Son gün" sütunu).
Yazar: hiçbir şey (yalnızca ekrana).
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

TARIH = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")


def tablo_satirlari(md):
    """Markdown tablolarını [ {başlık: değer} ] olarak döndürür."""
    sonuc, baslik = [], None
    for satir in md.splitlines():
        s = satir.strip()
        if not (s.startswith("|") and s.endswith("|")):
            baslik = None
            continue
        hucre = [h.strip() for h in s.strip("|").split("|")]
        if baslik is None:
            baslik = hucre
        elif set("".join(hucre)) <= set("-: "):
            continue
        else:
            sonuc.append(dict(zip(baslik, hucre)))
    return sonuc


def kunye(dava_md):
    k = {}
    for r in tablo_satirlari(dava_md):
        vals = list(r.values())
        if len(vals) >= 2:
            k[vals[0]] = vals[1]
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("davalar", nargs="?", default=str(Path(__file__).resolve().parents[2] / "davalar"))
    ap.add_argument("--gun", type=int, default=30, help="kaç gün içindeki süreler gösterilsin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    bugun = dt.date.today()
    kok = Path(a.davalar)
    sureler, ozet = [], []
    for d in sorted(p for p in kok.iterdir() if p.is_dir() and not p.name.startswith("_")):
        k = kunye((d / "dava.md").read_text("utf-8")) if (d / "dava.md").exists() else {}
        ozet.append({"dava": d.name, "asama": k.get("Aşama", ""), "son_durum": k.get("Son durum", ""),
                     "guncelleme": k.get("Son güncelleme", "")})
        if not (d / "sureler.md").exists():
            continue
        for r in tablo_satirlari((d / "sureler.md").read_text("utf-8")):
            hucre = r.get("Son gün", "") or next(iter(r.values()), "")
            m = TARIH.search(hucre)
            durum = r.get("Durum", "")
            if not m or re.search(r"yapıldı|tamam|bitti", durum, re.I):
                if not m and hucre and not set(hucre) <= set("-: "):
                    sureler.append({"dava": d.name, "tarih": None, "kalan": None, "islem": r.get("İşlem", ""),
                                    "not": hucre, "durum": durum})
                continue
            t = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            sureler.append({"dava": d.name, "tarih": t.isoformat(), "kalan": (t - bugun).days,
                            "islem": r.get("İşlem", ""), "not": hucre, "durum": durum})
    sureler.sort(key=lambda x: (x["kalan"] is None, x["kalan"] if x["kalan"] is not None else 0))
    if a.json:
        print(json.dumps({"bugun": bugun.isoformat(), "sureler": sureler, "davalar": ozet}, ensure_ascii=False, indent=1))
        return
    print(f"# Portföy — {bugun:%d.%m.%Y}\n")
    print(f"## Süreler (geçmiş ve {a.gun} gün içi)\n| Durum | Son gün | Kalan | Dava | İşlem |\n|---|---|---|---|---|")
    for s in sureler:
        if s["kalan"] is None:
            continue
        if s["kalan"] <= a.gun:
            isaret = "⛔ GEÇTİ" if s["kalan"] < 0 else "🔴 ACİL" if s["kalan"] <= 7 else "🟠" if s["kalan"] <= 14 else "🟢"
            print(f"| {isaret} | {dt.date.fromisoformat(s['tarih']):%d.%m.%Y} | {s['kalan']} | {s['dava']} | {s['islem']} |")
    tarihsiz = [s for s in sureler if s["kalan"] is None]
    if tarihsiz:
        print("\n## Tarihi belirsiz süreler (hesaplanmalı)\n| Dava | İşlem | Not |\n|---|---|---|")
        for s in tarihsiz:
            print(f"| {s['dava']} | {s['islem']} | {s['not']} |")
    print("\n## Davalar\n| Dava | Aşama | Son durum | Güncelleme |\n|---|---|---|---|")
    for o in ozet:
        print(f"| {o['dava']} | {o['asama']} | {o['son_durum']} | {o['guncelleme']} |")


if __name__ == "__main__":
    main()
