---
name: durusma-hazirlik
description: Duruşma hazırlığı — tanık soru listesi, müvekkilin dinlenmesine hazırlık, hâkimin soracağı sorular, sunulacak belge listesi ve sözlü beyan iskeleti. "Duruşmaya hazırla", "tanık soruları", "müvekkil dinlenecek", "duruşmada ne söyleyeyim" isteklerinde kullan.
---

# Duruşma Hazırlığı

(claude-for-legal `deposition-prep` yapısından Türk yargılamasına uyarlandı — Apache 2.0.)

Önce `temel-ilkeler` (§11 kayıt sadakati ve tanık beyanı kuralları dahil) uygulanır.

## Girdi
Dava klasörü: `dava.md`, `olay.md`, `kronoloji.md`, son analiz (özellikle §6 ispat tablosu, §7 karşı taraf,
§8 hâkim gözü), `belgeler-metin/`. Duruşma tarihi ve gündemi (tensip / ara karar) sorulur veya `sureler.md`'den alınır.

## Çıktı: `analiz/<tarih>-durusma-<YYYY-AA-GG>.md`

1. **Duruşmanın amacı (tek cümle):** Bu celsede ne elde edilmeli? (ara karar, tanık dinletme, bilirkişi, sevk…)
2. **Sözlü beyan iskeleti (en fazla 1 sayfa):** en güçlü nokta başta, 3–4 konu; her konu için dayanak belge (Ek-n).
   Atıflar yalnızca ✓ olanlardan; okunacak alıntılar birebir.
3. **Hâkimin soracağı muhtemel sorular** ve her birine kısa, doğru cevap (analiz §8'den).
4. **Müvekkil/kısıtlı/sanık dinlenecekse:** onu bekleyen sorular ve **neyi anlatması gerektiği değil, neyi
   bildiğinin** ortaya çıkması için hazırlık soruları. Ezber cevap hazırlanmaz.
5. **Tanık listesi ve soru blokları:** her tanık için
   - neyi ispat ediyor (ispat tablosundaki unsur),
   - **ispat edici sorular** (açık uçlu: "ne gördünüz", "ne zamandan beri tanıyorsunuz"),
   - **riskli alanlar** (tanığın bilmediği veya zayıf olduğu konular — sorulmaz),
   - karşı tarafın tanığına yöneltilecek sorular: çelişki noktaları ve dayanağı (belge/tutanak; alıntı yalnızca kayıtta varsa).
   > Türk yargılamasında sorular kural olarak hâkim aracılığıyla veya hâkimin izniyle yöneltilir; usul maddesi
   > gerekiyorsa Mütalaa ile doğrulanarak eklenir.
6. **Sunulacak belgeler:** liste + kaç nüsha + dosyada var mı / ilk kez mi sunulacak (süre ve ön inceleme
   yasağı riski varsa uyarı).
7. **Talepler listesi (tutanağa geçirtilecek):** her talep tek cümle, dayanağıyla.
8. **Kriz senaryoları:** tanık gelmezse, karşı taraf yeni belge sunarsa, hâkim ret eğilimindeyse — her biri için tek satırlık hamle.

## Kurallar
- Tanık veya müvekkil adına beyan metni **yazılmaz**; yalnızca soru ve hatırlatıcı başlık.
- Gizli strateji (risk matrisi, karşı taraf analizi) müvekkile veya tanığa verilecek nüshaya konmaz (§11.4).
- Uzun liste ≠ iyi hazırlık: her blok en fazla 5–7 soru; ötesi "yedek" başlığına.
