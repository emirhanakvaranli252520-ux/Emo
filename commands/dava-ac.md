---
description: Yeni dava klasörü açar (şablondan), belgelerin metnini çıkarır, künye/olay/kronoloji taslağını doldurur
argument-hint: <kısa-ad> [hukuk alanı] [temsil edilen taraf]
---

# /emo:dava-ac

Girdi: $ARGUMENTS

1. **Kod üret:** `<YYYY>-<sıra>-<kısa-ad>` (sıra: `davalar/` altında o yıl açılmış klasör
   sayısı + 1, üç haneli). Kısa adda Türkçe karakter yerine ASCII ve tire kullan.
2. **Klasörü oluştur:** `davalar/_sablon/` içeriğini `davalar/<kod>/` altına kopyala.
3. **Belgeler:** Kullanıcı belge verdiyse `belgeler/` altına koy; UDF/PDF/DOCX metinlerini
   `belgeler-metin/` altına çıkar. (UDF bir ZIP arşividir; metin `content.xml` içindedir.)
4. **Doldur:**
   - `dava.md`: alan, dava türü, temsil ettiğimiz taraf, taraflar, mahkeme, esas no, aşama.
     Bilinmeyen alanları boş bırak; tahmin etme.
   - `olay.md`: müvekkil anlatımı ile belgeden tespit edilen olguları ayrı başlıklarda.
   - `kronoloji.md`: belgelerdeki bütün tarihli olaylar; her satırda kaynak belge.
   - `sureler.md`: belgelerde görünen tebliğ/karar tarihlerinden doğan süreler için
     `/emo:sure` mantığıyla ilk hesap.
5. **Kullanıcıya:** Klasör yolu, eksik bilgiler (özellikle temsil edilen taraf, tebliğ tarihleri)
   ve bir sonraki adım önerisi: `/emo:analiz <kod>`.
