---
description: Bir hukuki soru için lehe ve aleyhe içtihat taraması (arşiv + 11M korpus + güncel resmî kaynak), doğrulanmış emsal tablosu
argument-hint: <hukuki soru veya olay özeti> [--daire "9. Hukuk"] [--yil 2018-]
---

# /emo:ictihat

Soru: $ARGUMENTS

`temel-ilkeler`, `kaynak-dogrulama`, `ictihat-arsivi` ve `ictihat-korpusu` skill'lerini yükle.

1. **Soruyu ayrıştır:** Hukuki sorun(lar), ilgili daire(ler), dönem. Temsil ettiğimiz taraf
   biliniyorsa "lehe" ve "aleyhe" bu tarafa göre belirlenir.
2. **Tara (üç kaynak):**
   - `ictihat-arsivi`: soruyu olay diliyle bir cümleye çevirip anlamsal ara; ardından karşı tezi
     anlatan cümleyle tekrar ara.
   - `ictihat-korpusu`: anahtar ifadelerle (`ara`), gerekirse AYM ve BAM (`--kaynak aym_bb emsal`).
   - Mütalaa `karar_ara`: `date_from` ile 2025 sonrası güncel kararlar; HGK/CGK/İBK için `chamber`.
3. **Seç:** Sorun başına 3–5 karar; öncelik temel-ilkeler §3 sırasıyla. Gönderme, görevsizlik
   gibi usul kararlarını emsal sayma.
4. **Doğrula:** Seçilen her kararı `belge_getir` ile tam metinden oku; künye ve tarihi metinden al;
   sonucu yaz; ilkeyi gösteren kısa alıntıyı birebir al.
5. **Çıktı:**

```markdown
# İçtihat Taraması — <soru>
## Kısa cevap
## Lehe kararlar
| Karar künyesi | İlke (birebir alıntı) | Sonuç | Kaynak | Durum |
## Aleyhe kararlar ve ayrışma yolu
| Karar künyesi | İlke | Nasıl ayrışırız | Kaynak | Durum |
## Güncel çizgi (son 2 yıl) ve içtihat değişikliği notu
## Taranan kaynaklar ve sorgular
```

Dava klasörü verildiyse raporu `analiz/<tarih>-ictihat-<konu>.md` olarak kaydet ve ✓ kararları
`kaynaklar.md`'ye ekle.
