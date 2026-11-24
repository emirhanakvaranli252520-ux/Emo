---
description: Usul süresi hesabı (dava, cevap, istinaf, temyiz, itiraz, işe iade, zamanaşımı…) — adli tatil ve resmî tatil kontrolüyle
argument-hint: <işlem> <başlangıç olayı ve tarihi> [dava klasörü kodu]
---

# /emo:sure

Girdi: $ARGUMENTS

`temel-ilkeler` ve `kaynak-dogrulama` skill'lerini yükle.

1. **İşlemi ve başlangıç olayını belirle:** Tebliğ, öğrenme, karar tarihi, son tutanak vb.
   Tebliğ türü (fiziki / e-tebligat) önemliyse belirt; belli değilse sor veya iki ihtimali hesapla.
2. **Süreyi ve dayanağını doğrula:** İlgili maddeyi Mütalaa `mevzuat_madde_getir` ile çek;
   süreyi madde metninden al (hafızadan değil). Hak düşürücü süre / zamanaşımı ayrımını yaz.
3. **Hesapla:** Soorgla süre hesaplama ve tatil kontrolü araçlarıyla (adli tatil, resmî tatil,
   son günün tatile denk gelmesi). Araç yoksa hesap adımlarını tek tek göster ve sonucu ⚠ işaretle.
4. **Çıktı:**

| Son gün | İşlem | Süre | Dayanak | Başlangıç | Hesap notu | Kalan gün |
|---|---|---|---|---|---|---|

   Bugünden itibaren kalan gün sayısını yaz; 7 günden azsa **ACİL** işaretle.
5. Dava klasörü verildiyse `sureler.md` tablosuna ekle.
