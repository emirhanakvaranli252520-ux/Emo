---
description: Dilekçe taslağı (dava, cevap, istinaf, temyiz, itiraz, ihtarname…) — zorunlu atıf denetimi ve antetli UDF ile
argument-hint: <dilekçe türü> [dava klasörü kodu] [ek talimat]
---

# /emo:dilekce

Girdi: $ARGUMENTS

Önce `temel-ilkeler` ve `kaynak-dogrulama` skill'lerini yükle. Üslup için
`temel-ilkeler/references/uslup.md` dosyasını **baştan sona** oku ve uygula.

## 1. Hazırlık
1. Dilekçe türünü belirle (dava · cevap · cevaba cevap · ikinci cevap · istinaf · temyiz ·
   itiraz · tedbir/haciz talebi · bilirkişi raporuna itiraz · ihtarname · şikâyet · diğer).
2. Dava klasörünü oku: `dava.md`, `olay.md`, `kronoloji.md`, son analiz raporu,
   `strateji.md`, `sureler.md`, `kaynaklar.md`, ilgili `belgeler-metin/`.
   Analiz raporu yoksa kullanıcıya önce `/emo:analiz` önerilir; kullanıcı isterse doğrudan devam edilir.
3. **Süre:** Dilekçenin son günü `sureler.md`'de yoksa hesapla (Soorgla süre aracı) ve en üstte göster.
4. **Zorunlu unsurlar:** Dilekçe türüne göre usul kanunundaki zorunlu unsurları Mütalaa ile
   madde metninden çıkar (ör. dava dilekçesi ve cevap dilekçesinin içeriğini düzenleyen
   HMK maddeleri) ve bir kontrol listesi yap.

## 2. Taslak
- Yapı: Mahkeme başlığı · taraflar ve vekiller · konu · açıklamalar · hukuki sebepler ·
  hukuki deliller · sonuç ve istem · ekler.
- Her iddia: olgu → delil (Ek-n) → hukuk kuralı → sonuç.
- **Yalnızca `kaynaklar.md` içinde veya bu oturumda resmî kaynaktan ✓ ile doğrulanmış atıflar
  kullanılır.** Yeni atıf gerekiyorsa önce `kaynak-dogrulama` ile doğrula.
- Karşı tarafın muhtemel savunmalarını (analiz §7) önceden ve ölçülü biçimde karşıla.
- Talep sonucu açık, belirli ve infaz edilebilir olsun.
- Taslağı `dilekceler/<YYYY-AA-GG>-<tür>-taslak.md` olarak kaydet.

## 3. Zorunlu atıf denetimi
`atif-dogrulayici` ajanını (Agent aracında `emo:atif-dogrulayici`) taslak üzerinde çalıştır.
- ✗ atıf → metinden çıkar. ⚠ atıf → düzelt veya çıkar. Mahkeme metnine ⚠ işareti konmaz.
- Düzeltmeden sonra yalnızca değişen atıflar için denetimi tekrarla.
- Sonuç "MAHKEMEYE SUNULABİLİR" değilse dilekçeyi kesinleştirme; kalan sorunları kullanıcıya listele.

## 4. Üslup kontrolü
`uslup.md` sonundaki teslim öncesi kontrol listesini madde madde uygula.

## 5. Çıktı
1. Kesin metin: `dilekceler/<YYYY-AA-GG>-<tür>.md`
2. Antetli UDF: `akvaranli-udf-antet` skill'i mevcutsa onunla `dilekceler/<YYYY-AA-GG>-<tür>.udf`.
   Mevcut değilse bunu söyle ve yalnızca metni teslim et.
3. Atıf denetim tablosu: `dilekceler/<YYYY-AA-GG>-<tür>-atif-denetimi.md`
4. Kullanıcıya: süre son günü, atıf denetimi özeti, dosya yolları ve avukatın son kontrol
   etmesi gereken noktalar (varsayımlar, eksik ekler).
