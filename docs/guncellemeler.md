# Güncelleme Notları

Her önemli değişiklik burada tarih sırasıyla (yeniden eskiye) özetlenir. Yeni oturumlar sistemi tanımak için okuyabilir.

## 28.11.2026 — claude-for-legal uyarlamaları, Mizan test vakaları, kritik düzeltme

### Kritik düzeltme: ihtarname zamanaşımını KESMEZ
- TBK m.154 ✓ zamanaşımını kesen sebepleri sınırlı sayar: borçlunun ikrarı (faiz ödeme, kısmi ifa, rehin, kefil),
  dava veya def'i, hakeme başvuru, icra takibi, iflas masasına başvuru. **İhtarname bunlar arasında yoktur.**
- İhtarname, muaccel borçta borçluyu temerrüde düşürür — TBK m.117 ✓.
- Stratejist talimatındaki ve tasarım belgesindeki "ihtarname ile zamanaşımını kesme" ifadesi düzeltildi;
  `kaynak-dogrulama` tuzaklar listesine eklendi: usul/süre sonucu doğuran her kural madde metninden doğrulanır.

### claude-for-legal (Anthropic, Apache 2.0) — tasarım kaynağı
İçerik ABD hukukuna göredir, doğrudan kullanılmaz; aşağıdakiler Türk hukukuna uyarlandı:
| Eklenen | Ne yapıyor |
|---|---|
| `temel-ilkeler` §11 (4 kural) | Tırnak içi alıntı yalnızca kayıtta birebir varsa · tanık/müvekkil beyanı onun ağzından yazılmaz · dışarı gidecek metne iç strateji konmaz · duruşma metinlerinde en önemli 3–4 konu |
| `durusma-hazirlik` | Duruşma amacı, sözlü beyan iskeleti, hâkimin soruları, tanık soru blokları, belge listesi, kriz senaryoları |
| `delil-muhafaza` | Silinme riski olan deliller için envanter + son gün + önlem; HMK m.400 ✓ (delil tespiti), CMK m.134 ✓ (dijital delil kopyası) |
| `ihtarname` | İhtarname yazma ve gelen ihtarnameye cevap; TBK m.117 ✓, TBK m.154 ✓ |
| `/emo:durum` + `araclar/portfoy/portfoy.py` | Bütün davaların süre ve duruşma tablosu (⛔ geçti · 🔴 ≤7 gün · 🟠 ≤14 · 🟢) |
Referans kopya: `docs/kaynak/claude-for-legal/` (içindeki CLAUDE.md dosyaları `CLAUDE.kaynak.md` olarak etkisizleştirildi).

### Mizan-27B (AlicanKiraz0, CC-BY-NC-4.0)
- Karar aracı olarak **alınmadı**: gerekçe/kaynak üretmez; çalıştırmak için 52 GB GPU ya da olay metnini herkese açık
  üçüncü taraf sunucuya göndermek gerekir (sır saklama); ticari olmayan kullanım şartı.
- **20 zor vaka + soru bankası** test seti olarak alındı (`evals/indir.sh`; lisans gereği repoya konmaz).

## 27.11.2026 — İçe aktarma
- `/emo:ice-aktar` + `araclar/envanter/envanter.py`: bir klasörü salt okunur inceler, envanter çıkarır, evrakı
  sınıflandırarak `kutuphane/` (git dışı) ve `davalar/` altına alır.

## 25–26.11.2026 — Kalıcılık
- `CLAUDE.md` (proje talimatı), `araclar/KUR-EMO.bat` (Windows tek tık kurulum), tez süzme aracı.

## 24.11.2026 — Korpus doğrulama ve ilk gerçek dosya
- 11 milyon kararlık korpus; 107/107 karar metni resmî metinle aynı; kayıt bilgisi hataları ölçüldü
  (`docs/korpus-dogrulama-raporu.md`). Kural: künye ve tarih yalnızca kararın kendi metninden.
- Atıf doğrulayıcı ajan: iki temiz testte 10/10.
- 4 bakış açısı ajanı ve 7 komut.
