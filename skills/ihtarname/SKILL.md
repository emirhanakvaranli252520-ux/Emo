---
name: ihtarname
description: İhtarname yazma (noter/KEP) ve karşı taraftan gelen ihtarnameyi değerlendirip cevap hazırlama. "İhtarname çek", "ihtar yaz", "gelen ihtarnameye cevap", "temerrüde düşür" isteklerinde kullan.
---

# İhtarname

(claude-for-legal `demand-draft` / `demand-received` akışından uyarlandı — Apache 2.0.)

Önce `temel-ilkeler` (§11 dahil) ve `kaynak-dogrulama` uygulanır. Üslup: `temel-ilkeler/references/uslup.md`
(vakar, insaf, kelamda iktisat — tehdit dili yok).

## A. İhtarname yazma

**1. Amaç tespiti (önce bu):** Bu ihtar hangi hukuki sonucu doğuracak?
| Amaç | Not |
|---|---|
| Temerrüt | Muaccel borçta borçlu alacaklının ihtarıyla temerrüde düşer — TBK m.117/1 ✓. Belirli vade günü kararlaştırılmışsa ihtar gerekmez (m.117/2 ✓) |
| Süre verme / fesih ön şartı | Sözleşme veya kanun ihtar ve süre şartı arıyorsa, şartın içeriği madde metninden alınır |
| Delil muhafaza / kötüniyetin belgelenmesi | bkz. `delil-muhafaza` |
| Zamanaşımını kesme | **İhtarname zamanaşımını KESMEZ** — TBK m.154 ✓ (kesen sebepler: ikrar, dava/def'i, hakeme başvuru, icra takibi, iflas masası). Bu amaç varsa ihtar yerine dava veya icra takibi önerilir |
| Arabuluculuk / dava öncesi uzlaşma çağrısı | Dava şartı arabuluculuk varsa ihtar onun yerine geçmez |

**2. İçerik:** keşideci ve muhatap (tam unvan, adres; KEP adresi varsa) · olgular (kısa, tarihli, belgeli) ·
hukuki dayanak (yalnızca ✓ madde) · talep (açık, belirli, ölçülebilir: tutar, süre, eylem) · süre (makul, sözleşme/kanun
şartına uygun) · sonuç bildirimi (yasal yollara başvurulacağı — abartısız) · tarih/imza.
- Gereksiz hukuki argüman ve **iç strateji** ihtarnameye yazılmaz; ihtarname karşı tarafın elinde delildir.
- Karşı tarafı küçük düşüren veya ceza tehdidi içeren ifade yok.

**3. Gönderim notu:** noter / KEP / iadeli taahhütlü — tebliğ tarihinin ispatı ve süre hesabı için hangisinin
uygun olduğu kullanıcıya not edilir; süre `/emo:sure` ile hesaplanır ve `sureler.md`'ye işlenir.

## B. Gelen ihtarnameyi değerlendirme

1. **Tebliğ tarihi** ve ihtarda verilen süre → son gün (`/emo:sure`), `sureler.md`'ye ACİL satırı.
2. **Ne istiyor, hangi sonucu doğurmaya çalışıyor?** (temerrüt, fesih ön şartı, süre başlatma, delil oluşturma)
3. **Doğru mu?** Olgular ve dayanak — atıflar `atif-dogrulayici` ile denetlenebilir (`/emo:atif-denetle`).
4. **Cevap gerekli mi?** Susmanın sonucu (ör. sözleşmede kabul sayılma hükmü) ile cevabın riski (ikrar sayılabilecek ifade) tartılır.
5. **Cevap taslağı** (gerekiyorsa): iddiaları kabul anlamına gelecek ifadelerden kaçınan, olguları düzelten, kısa metin.

## Çıktı
`dilekceler/<tarih>-ihtarname-<konu>.md` + gönderim ve süre notu; atıf varsa denetim tablosu.
