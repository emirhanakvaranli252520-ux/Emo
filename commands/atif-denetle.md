---
description: Herhangi bir metindeki (kendi dilekçemiz, karşı tarafın dilekçesi, bilirkişi raporu, karar) bütün atıfları resmî kaynaktan denetler
argument-hint: <dosya yolu veya metin>
---

# /emo:atif-denetle

Girdi: $ARGUMENTS

1. Girdi bir dosya yoluysa dosyayı oku (UDF/PDF/DOCX ise önce metnini çıkar); değilse girdiyi metin say.
2. Agent aracıyla `emo:atif-dogrulayici` ajanını çağır (görünmüyorsa `atif-dogrulayici`).
   Ajana metni veya dosya yolunu ve raporu yazacağı yolu ver:
   aynı klasörde `<dosya-adı>-atif-denetimi.md` (metin verildiyse `davalar/_gecici-<tarih>/`).
3. Kullanıcıya: sonuç satırı, ✓/⚠/✗/? sayıları, ✗ ve ⚠ olanların listesi ve rapor yolu.
4. Denetlenen metin **karşı tarafın** ise ✗ ve ⚠ atıfları ayrıca "karşı tarafa yöneltilebilecek
   itirazlar" başlığıyla listele (ör. "davalı vekilinin dayandığı … kararı resmî kaynakta
   bulunmamaktadır"). Bu itirazların dilini `uslup.md`'ye göre ölçülü tut.
