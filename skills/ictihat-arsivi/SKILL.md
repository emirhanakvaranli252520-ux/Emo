---
name: ictihat-arsivi
description: Yerel içtihat arşivinde (≈700 bin Yargıtay ve Danıştay kararı, 2006–2025 ortası) sorgu sınırı olmadan emsal karar BULMA - anlamsal arama, esas/karar no ile arama, ifade araması, tam metin. Emsal karar, içtihat, Yargıtay kararı, benzer karar, aleyhe karar araması gereken her işte ilk adım olarak kullan; bulunan kararı resmî kaynaktan teyit et.
---

# İçtihat Arşivi (yerel, sınırsız — bulma aracı)

Kaynak: Hugging Face `muhamparlak/turkish-law-bge-m3-embeddings` (CC-BY-4.0). Kararların aslı
Yargıtay ve Danıştay'ın kamuya açık karar sistemlerinden derlenmiştir.

- ≈1,82 milyon parça · Yargıtay (Hukuk + Ceza daireleri, kapatılan daireler dahil) ve Danıştay
- Kararların çoğu 2006–2025 ortası arası

**Doğrulama testi (24.11.2026):** Üç rastgele kararın arşiv metni, resmî Bedesten metniyle
karakter düzeyinde birebir aynı çıktı. Arşivdeki `doc_id`, resmî Bedesten kimliğinin aynısıdır.

> Arşivin mevzuat kümesi **kullanılmaz**: resmî metinle karşılaştırmada madde metni atladığı
> tespit edildi. Mevzuat yalnızca `kaynak-dogrulama` skill'indeki resmî kaynaklardan alınır.

## Ne zaman kullanılır

- **İçtihat taramasında ilk adım budur.** Sorgu sınırı yoktur.
- Lehe **ve aleyhe** emsal arama, bir dairenin yerleşik çizgisini görme.
- Künyesi bilinen bir kararın (esas veya karar no) metnini bulma.
- Belirli bir ifadenin (ör. "muris muvazaası") hangi kararlarda geçtiğini bulma.

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
```

Süzgeçler: `--kaynak Yargıtay|Danıştay`, `--daire "<parça>"`, `--yil-min`, `--yil-max`, `-k`.
Ajanlar için makine okunur çıktı: `--json`.

## Arama yöntemi

1. **Sorguyu olay diliyle yaz.** "İşçi performans düşüklüğü gerekçesiyle savunması alınmadan
   çıkarıldı" gibi bir cümle, anahtar kelime yığınından daha iyi sonuç verir.
2. **Lehe ve aleyhe ayrı ara.** Aynı sorunu karşı tarafın tezini anlatan bir cümleyle bir kez
   daha sorgula.
3. **Daire süzgecini dar tutma.** Dairelerin görev alanları yıllar içinde değişti, bazı
   daireler kapatıldı. Emin değilsen süzgeçsiz ara, sonra daireye göre ele.
4. **Güncel çizgi:** Arşiv 2025 ortasında biter. Sonuç için önemli her konuda, Mütalaa
   `karar_ara` ile `date_from` kullanarak 2025 sonrası kararlar da taranır.
5. **Tam metni oku.** Raporda kullanılacak her kararı `--tam` ile aç; ilkeyi ve **sonucu**
   (onama/bozma, kimin lehine) metinden teyit et.

## Doğrulama durumu

| Durum | Ne zaman | Nerede kullanılabilir |
|---|---|---|
| **✓** | Mütalaa `belge_getir {"id": "bedesten:<doc_id>"}` ile resmî metin çekildi ve kontrol edildi | Her yerde, mahkeme metni dahil |
| **✓ arşiv** | Arşivde tam metin okundu, ilke metinde birebir var | Yalnızca analiz raporu |
| **⚠ DOĞRULANMADI** | Yalnızca özet görüldü veya künye bulunamadı | Mahkeme metnine giremez |

## Kurulum (bir kez)

```bash
pip install -r scripts/requirements.txt
python3 scripts/indir.py          # ≈5 GB indirir, işlenmiş arşiv ≈3,5 GB yer kaplar
```

Arşiv kurulu değilse betik bunu söyler. Bu durumda kurulum komutunu kullanıcıya hatırlat ve
aramayı Mütalaa `karar_ara` ile sürdür.
