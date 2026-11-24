---
description: Hızlı kırmızı takım — karşı tarafın muhtemel savunma, usul ve hileli hamleleri ile bunlara karşı hukuka uygun emniyet tedbirleri
argument-hint: <dava klasörü kodu veya olay metni>
---

# /emo:karsi-taraf

Girdi: $ARGUMENTS

1. Dava klasörünü veya olay metnini oku; temsil ettiğimiz taraf belli değilse yalnızca bunu sor.
2. Agent aracıyla `emo:karsi-taraf` ajanını çağır; çıktıyı `analiz/_calisma/<tarih>/karsi-taraf.md`
   dosyasına yazdır.
3. Ardından `emo:stratejist` ajanını **yalnızca 9.1 (emniyet tedbirleri), 9.2 (taktik sıra) ve
   9.4 (süre takvimi)** bölümleri için çağır.
4. `emo:atif-dogrulayici` ile iki çıktının atıflarını denetle.
5. Kullanıcıya: en tehlikeli 3 hamle, her birine karşı tedbir ve son gün, ACİL olanlar,
   atıf denetimi özeti. Tam analiz için `/emo:analiz` öner.
