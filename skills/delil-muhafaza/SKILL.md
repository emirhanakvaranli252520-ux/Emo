---
name: delil-muhafaza
description: Delillerin kaybolmadan korunması — müvekkilin kendi delillerini toplama listesi, silinme riski olan kayıtlar (kamera, HTS, yazışma, banka, sunucu kaydı) için muhafaza talepleri, delil tespiti ve dijital delil imajı. "Delil kaybolmasın", "kamera kaydı silinecek", "delil tespiti", "yazışmaları koru" isteklerinde ve her yeni dosyanın başında kullan.
---

# Delil Muhafaza

(claude-for-legal `legal-hold` mantığından uyarlandı — Apache 2.0. Türk usul hükümleri Mütalaa ile doğrulanır.)

Önce `temel-ilkeler` ve `kaynak-dogrulama` uygulanır.

## 1. Envanter — hangi delil, kimde, ne zaman yok olur?

| Delil | Kimde | Silinme / kaybolma riski | Önlem | Son gün |
|---|---|---|---|---|

Sık rastlanan **kısa ömürlü** deliller (tablo bunlarla doldurulur, olaya göre):
- Kamera kayıtları (işyeri, site, belediye, banka) — kayıt üzerine yazma döngüsü kısa olabilir
- Telefon görüşme/HTS ve baz kayıtları, internet trafik kayıtları — saklama süreleri sınırlıdır
- Mesajlaşma uygulaması yazışmaları, e-postalar, sosyal medya içerikleri (silinebilir, hesap kapanabilir)
- Banka hareketleri, POS kayıtları, şirket muhasebe/sunucu kayıtları
- Fiziki iz ve durum (inşaat ayıbı, hasar, işyerindeki fiili durum) — değişebilir
- Tanıkların hafızası ve ulaşılabilirliği (yurt dışına gidecek, yaşlı, hasta)

> Saklama süreleri mevzuata ve kuruma göre değişir; somut süre **tahmin edilmez**, gerekiyorsa ilgili
> düzenleme Mütalaa ile çekilir veya kurumdan yazılı bilgi istenir. Bilinmiyorsa "en kısa sürede" kabul edilir.

## 2. Araçlar (dayanaklar resmî metinden doğrulandı)

| Araç | Ne zaman | Dayanak |
|---|---|---|
| **Delil tespiti** | Dava açılmadan veya inceleme sırası gelmeden, delil kaybolacak/zorlaşacaksa: keşif, bilirkişi, tanık ifadesi | HMK m.400 ✓ — "delilin hemen tespit edilmemesi hâlinde kaybolacağı yahut ileri sürülmesinin önemli ölçüde zorlaşacağı ihtimal dâhilinde bulunuyorsa hukuki yarar var sayılır" |
| **Dijital delil imajı ve kopyası (ceza)** | Cihaza el konulduğunda | CMK m.134/3–4 ✓ — sistemdeki bütün verilerin yedeği alınır; yedekten bir kopya şüpheliye veya vekiline verilir ve tutanağa geçirilir |
| **Kurumlara muhafaza/ibraz talebi** | Kamera, HTS, banka kayıtları | Mahkeme/savcılık müzekkeresi; dava öncesinde ilgiliye yazılı başvuru (dayanak olaya göre Mütalaa ile) |
| **Noter tespiti / e-tespit** | İnternet içeriği, yazışma ekranı | Olaya göre; tespit tutanağının içeriği ve tarihi kayda geçer |
| **İhtarname** | Karşı tarafa "şu kayıtları silmeyin, saklayın" bildirimi | Delil karartmayı önlemez ama ileride kötüniyetin ispatına yarar; **zamanaşımını kesmez** (TBK m.154 ✓) |

## 3. Müvekkile verilecek "delil koruma" talimatı (sade dil)
- Telefon/bilgisayardaki ilgili yazışmaları **silmeyin**, cihazı değiştirmeyin/sıfırlamayın; yedek alın.
- Ekran görüntüsü yetmez: mümkünse yazışmanın tamamını dışa aktarın (tarih ve numara görünsün).
- Orijinal belgeleri avukata teslim edin; sizde fotokopi kalsın.
- Karşı tarafla bu konuda yeni yazışma başlatmayın; gelen mesajlara cevap vermeden önce avukata danışın.
- **Delil üretmeyin, düzeltmeyin, tarih değiştirmeyin.** (temel-ilkeler §2.4)

## 4. Çıktı
`strateji.md` → "Emniyet tedbirleri" tablosuna her delil için satır; `sureler.md` → kayıt silinme riski olan
deliller için **ACİL** satırı; gerekirse `/emo:dilekce` ile delil tespiti talebi veya müzekkere talepli dilekçe.
