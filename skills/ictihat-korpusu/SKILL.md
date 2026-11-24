---
name: ictihat-korpusu
description: 11 milyon kararlık yerel Türk İçtihat Korpusu (Yargıtay 1997–2026, Danıştay, UYAP Emsal/BAM 2017–2026, AYM norm ve bireysel başvuru) ile KÜNYE ÖN KONTROLÜ (böyle bir karar var mı?) ve Türkçe harf katlamalı TAM METİN ifade araması. Bir karar künyesi kullanılmadan önce, AYM veya BAM kararı aranırken, 2025 sonrası karar ya da belirli bir ifadenin geçtiği kararlar bulunurken kullan.
---

# İçtihat Korpusu (11 milyon karar, yerel)

Kaynak: Hugging Face `iaiauu/ictihatlar` — Hamza Bağırsakçı, 2026, **CC0-1.0**. Kararlar
kurumların kamuya açık arama sistemlerinden toplanmış; TCKN, IBAN, telefon gibi bilgiler
maskelenmiş. Fikir ve arayüz: karti.av.tr "İçtihat arama aracı".

| Kaynak (`--kaynak`) | Karar | Yıl |
|---|---:|---|
| `yargitay` | 9.820.145 | 1997–2026 |
| `danistay` | 386.608 | 1965–2026 |
| `emsal` (UYAP Emsal: BAM ve ilk derece) | 815.702 | 2017–2026 |
| `aym_norm` | 5.563 | 1962–2026 |
| `aym_bb` | 17.067 | 2012–2026 |

## İçtihat arşiviyle farkı

| | `ictihat-arsivi` | `ictihat-korpusu` (bu skill) |
|---|---|---|
| Arama türü | **Anlamsal** (olayı anlat, benzerini bul) | **İfade / künye** (birebir) |
| Kapsam | ≈700 bin karar, 2006–2025 | 11 milyon karar, AYM ve BAM dahil, 2026'ya kadar |
| En iyi kullanım | Emsal keşfi | Künye ön kontrolü, ifade taraması, AYM/BAM |

## Komutlar

Betik bu skill'in `scripts/` klasöründedir. Korpus dizini `$EMO_KORPUS` (yoksa `~/.emo/korpus`).
Ajanlar `--json` bayrağını komuttan **önce** verir: `python3 scripts/korpus.py --json kunye …`

```bash
# Künye ön kontrolü (indeksle anında)
python3 scripts/korpus.py kunye --esas 2022/2530 --karar 2022/4045 --daire "9. Hukuk"
python3 scripts/korpus.py kunye --esas 2021/964 --daire "Hukuk Genel"     # HGK 2021/7-964 E. → tireden öncesini at

# İfade araması (bütün ifadeler geçmeli; --veya ile herhangi biri)
python3 scripts/korpus.py ara "muris muvazaası" "tapu iptal" --kaynak yargitay --daire "1. Hukuk" --yil 2023- --limit 10

# Tam metin
python3 scripts/korpus.py oku yargitay:<document_id>
python3 scripts/korpus.py oku --esas 2022/2530 --karar 2022/4045 --daire "9. Hukuk"
```

**Arama ipuçları:**
- Türkçe harfler katlanır: "MURİS", "muris", "murıs" aynıdır.
- Harf dizisi arar: kök yazmak daha geniş tarar ("tescil" ⊃ "tesciline").
- `--daire "1. Hukuk"` 11. veya 21. Hukuk Dairesi'ni getirmez.
- Bütün korpusta ifade araması dakikalar sürebilir; `--kaynak`, `--daire`, `--yil` hızlandırır.

## Doğrulamadaki yeri (temel-ilkeler §4 ve `kaynak-dogrulama` ile)

Bu korpus **resmî kaynak değildir**; bulma ve ön kontrol aracıdır.

1. **Künye ön kontrolü:** Kullanılacak her karar künyesi önce burada aranır.
   - **Bulunamadıysa:** Künye büyük olasılıkla yanlış veya uydurmadır. Daire adını kaldırıp
     tekrar dene; yine yoksa künye **kullanılmaz**, Mütalaa ile resmî kaynakta aranır.
   - **Bulunduysa:** Künye var demektir, ama ✓ için resmî kaynaktan (`kaynak-dogrulama` §3)
     metin çekilir.
2. **AYM kararları:** Mütalaa `anayasa_karari_ara` ile resmî teyit.
3. **UYAP Emsal (BAM/ilk derece):** Mütalaa `karar_ara` `courts: ["istinaf"]` veya `["yerel"]`.
4. Korpustan alınan bir metin, resmî teyit yapılana kadar en fazla **"✓ arşiv"** düzeyindedir
   ve mahkeme metnine giremez.

## Kurulum (bir kez)

```bash
pip install -r scripts/requirements.txt
python3 scripts/korpus.py indir     # ≈5,5 GB, HTTPS; her dosya SHA-256 ile doğrulanır
python3 scripts/korpus.py indeks    # künye indeksi
python3 scripts/korpus.py durum
```

Veri seti sürümü betikte sabitlenmiştir; güncelleme bilinçli olarak `SURUM` değiştirilerek yapılır.
