---
name: ictihat-arsivi
description: Yerel içtihat arşivinde (≈700 bin Yargıtay ve Danıştay kararı, 2006–2025) sorgu sınırı olmadan anlamsal arama, esas/karar no ile bulma, ifade araması ve tam karar metni okuma. Emsal karar, içtihat, Yargıtay kararı, benzer karar, "bu konuda Yargıtay ne diyor", aleyhe karar araması gereken her işte Soorgla'dan ÖNCE kullan.
---

# İçtihat Arşivi (yerel, sınırsız)

Kaynak: Hugging Face `muhamparlak/turkish-law-bge-m3-embeddings` (CC-BY-4.0). Kararların aslı
Yargıtay ve Danıştay'ın kamuya açık karar arama sistemlerinden derlenmiştir.

| Küme | İçerik |
|---|---|
| `emsal` | ≈1,82 milyon parça · Yargıtay (Hukuk + Ceza daireleri, kapatılan daireler dahil) ve Danıştay · kararların çoğu 2006–2025 arası |
| `mevzuat` | 4.694 madde · Anayasa, TMK, TBK, TTK, TCK, CMK, HMK, İşK |

## Ne zaman kullanılır

- **İçtihat taramasında ilk adım budur.** Sorgu sınırı yoktur; Soorgla sorgu hakkını korur.
- Lehe **ve aleyhe** emsal arama, bir dairenin yerleşik çizgisini görme.
- Künyesi bilinen bir kararın (esas veya karar no) metnini bulma.
- Belirli bir ifadenin (ör. "muris muvazaası", "savunma alınmadan") hangi kararlarda geçtiğini bulma.

## Komutlar

Betikler bu skill'in `scripts/` klasöründedir. Arşiv dizini `$EMO_ARSIV` (yoksa `~/.emo/arsiv`).

```bash
# Anlamsal arama (ilk çalıştırmada BAAI/bge-m3 modeli iner, ~2,3 GB; sorgu ~20 sn)
python3 scripts/ara.py "<olayı ve hukuki sorunu anlatan 1–2 cümle>" --daire "9. Hukuk" --yil-min 2018 -k 8

# Esas veya karar no ile
python3 scripts/ara.py --esas 2022/2530 --daire "9. Hukuk"

# Karar metninde geçen ifade (model gerekmez, hızlı)
python3 scripts/ara.py --metin "muris muvazaası" --daire "1. Hukuk" --yil-min 2020 -k 10

# Kararın tam metni (doc_id sonuçlarda yazar)
python3 scripts/ara.py --tam 759068100

# Kanun maddesi ve mevzuatta anlamsal arama
python3 scripts/ara.py --kume mevzuat --madde "TMK 6"
python3 scripts/ara.py --kume mevzuat "boşanmada katılma alacağı"
```

Süzgeçler: `--kaynak Yargıtay|Danıştay`, `--daire "<parça>"`, `--yil-min`, `--yil-max`, `-k`.
Ajanlar için makine okunur çıktı: `--json`.

## Arama yöntemi

1. **Sorguyu olay diliyle yaz.** Karar metinleri olay ve gerekçe anlatır. "İşçi performans
   düşüklüğü gerekçesiyle savunması alınmadan çıkarıldı" gibi bir cümle, "İşK 19 performans"
   gibi anahtar kelimelerden daha iyi sonuç verir.
2. **Lehe ve aleyhe ayrı ara.** Aynı sorunu karşı tarafın tezini anlatan bir cümleyle bir kez
   daha sorgula.
3. **Daire süzgecini dar tutma.** Dairelerin görev alanları yıllar içinde değişti, bazı
   daireler kapatıldı ("(Kapatılan) 22. Hukuk Dairesi" gibi). Emin değilsen süzgeçsiz ara,
   sonra daireye göre ele.
4. **Güncel çizgi için yıl süzgeci** kullan (ör. `--yil-min 2020`), ama eski ve yerleşik bir
   ilke kararını da kaçırma.
5. **Sonuç özetine güvenme, tam metni oku.** Raporda kullanılacak her kararı `--tam` ile aç;
   kararın gerçekten o ilkeyi söylediğini ve **sonucunu** (bozma/onama, kimin lehine)
   metinden teyit et.
6. **Gerekçeden kısa alıntı** al; alıntı, kararın metnindeki ifadeyle birebir aynı olmalıdır.

## Doğrulama durumu (temel-ilkeler §4 ile birlikte)

| Durum | Ne zaman |
|---|---|
| **✓ arşiv** | Kararın künyesi ve metni arşivde bulundu, tam metin okundu, kullanılan ilke metinde birebir var |
| **⚠ DOĞRULANMADI** | Yalnızca özetten görüldü, tam metin okunmadı; veya künye arşivde bulunamadı |

**Sınırlar (raporda gerektiğinde belirt):**
- Arşiv **2025 ortasında** biter. Sonrasındaki içtihat değişiklikleri ve yeni İBK'lar burada yoktur.
  Sonuç için kritik bir konuda, güncel çizgi Soorgla `legal_search_cases` ile kontrol edilir.
- Arşivde HGK/CGK ve İBK kararları sınırlı olabilir; bunlar için Soorgla da taranır.
- **Mevzuat kümesi tarihi belirsiz bir anlık görüntüdür.** Madde bulmak için kullanılır,
  ama **✓ yalnızca Soorgla ile** verilir (yürürlük ve değişiklik geçmişi orada).
- Kişi adları kararlarda anonimdir ("..."); bu bir veri hatası değildir.

## Kurulum (bir kez)

```bash
pip install -r scripts/requirements.txt
python3 scripts/indir.py          # ≈5 GB indirir, işlenmiş arşiv ≈4,4 GB yer kaplar
```

Arşiv kurulu değilse betik bunu söyler. Bu durumda kurulum komutunu kullanıcıya hatırlat ve
içtihat aramasını Soorgla ile sürdür.
