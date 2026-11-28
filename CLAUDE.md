# Emo — Türk Hukuku Uzmanı (proje talimatı)

Bu repo, bir avukatın kullandığı Türk hukuku analiz sistemidir (Claude Code plugin'i "emo").
Kullanıcı avukattır; çıktılar mahkemeye sunulur. Bu dosyayı okuyan her oturum aşağıdakilere uyar.

## 1. Önce bunları oku (her oturumun başında, hukuki işten önce)
1. `skills/temel-ilkeler/SKILL.md` — anayasa: kırmızı çizgiler, doğrulama işaretleri (✓ / ✓ arşiv / ⚠ / ✎), muhakeme yöntemi
2. `skills/kaynak-dogrulama/SKILL.md` — resmî kaynak kullanımı ve mahkeme metni atıf denetimi
3. İş türüne göre: `skills/ictihat-korpusu/SKILL.md`, `skills/ictihat-arsivi/SKILL.md`,
   `skills/temel-ilkeler/references/uslup.md` (dilekçe), `skills/temel-ilkeler/references/cikti-formati.md` (analiz)

## 2. Değişmez kurallar (özet — ayrıntı temel-ilkeler'de)
- Hiçbir madde metni, karar künyesi veya alıntı **hafızadan** yazılmaz; bu oturumda resmî kaynaktan çekilir.
- **Künye ve karar tarihi yalnızca kararın kendi metninden** alınır. Arama sonuçlarındaki ve veritabanlarındaki
  kayıt bilgisi hatalı olabilir (ölçüldü: UYAP Emsal ≈%10 künye, resmî arama tarihi sıklıkla 1 gün erken).
- Mahkeme metnine yalnızca resmî kaynaktan doğrulanmış (✓) atıf girer; dilekçeler `atif-dogrulayici` denetiminden geçer.
- Bizim taraf için hileli yol önerilmez; karşı tarafın hileleri tespit edilir, hukuka uygun önlem üretilir.
- Mütalaa'ya kişi adı, TC no, adres, gizli dosya numarası gönderilmez; sorgular soyut hukuki terimlerle yapılır.

## 3. Araçlar ve veriler
| Kaynak | Ne için | Nasıl |
|---|---|---|
| **Mütalaa MCP** (`.mcp.json`, komut: `mutalaamcp serve`) | Resmî mevzuat ve karar metni — birincil doğrulama | Araçlar `mcp__mutalaa__*` veya `mcp__plugin_emo_mutalaa__*` |
| **İçtihat korpusu** (11 milyon karar) | Künye ön kontrolü, ifade araması, AYM/BAM | `python skills/ictihat-korpusu/scripts/korpus.py --json kunye …` |
| **İçtihat arşivi** (≈700 bin karar) | Anlamsal emsal arama | `python skills/ictihat-arsivi/scripts/ara.py "<olay cümlesi>"` |
| **Soorgla MCP** (günlük sınırlı) | Süre, harç, faiz, vekâlet ücreti, işçilik alacağı hesapları; madde sürüm geçmişi | claude.ai bağlayıcısı |

**Veri konumları:** korpus `~/.emo/korpus` (`$EMO_KORPUS`), arşiv `~/.emo/arsiv` (`$EMO_ARSIV`).
Windows'ta `~` = `C:\Users\<kullanıcı>`; Python komutu `py -3.12`.

**Oturum başında hızlı kontrol** (kullanıcı hukuki iş istediğinde, bir kez):
- `python skills/ictihat-korpusu/scripts/korpus.py durum` → korpus ve indeks var mı
- Mütalaa araçları görünüyor mu
- Eksik varsa kullanıcıya söyle ve kurulum komutunu öner (README "Kurulum"; Windows: `araclar/KUR-EMO.bat`).
  Bulut oturumunda korpus yoksa: `korpus.py indir && korpus.py indeks` (≈5,5 GB, SHA-256 doğrulamalı).

## 4. Komutlar ve ajanlar
Plugin yüklüyse: `/emo:dava-ac`, `/emo:analiz`, `/emo:karsi-taraf`, `/emo:ictihat`, `/emo:sure`, `/emo:dilekce`,
`/emo:atif-denetle`. Ajanlar: `emo:analist`, `emo:karsi-taraf`, `emo:hakim`, `emo:stratejist`, `emo:atif-dogrulayici`.

**Plugin yüklü değilse** (komutlar görünmüyorsa): aynı işi dosyalardan yürüt — komutun talimatı
`commands/<ad>.md`, ajanın talimatı `agents/<ad>.md`. Ajanı genel amaçlı bir alt ajanla çalıştırırken ona
önce ilgili `agents/<ad>.md` ve §1'deki skill dosyalarını okumasını söyle. Kullanıcıya plugin kurulumunu da öner:
`/plugin marketplace add <bu klasör>` → `/plugin install emo@emo-hukuk`.

## 5. Dava klasörleri
- Her dosya `davalar/<YYYY>-<sıra>-<kısa-ad>/` altında; şablon `davalar/_sablon/`.
- İşe başlamadan önce `dava.md`, `strateji.md`, `sureler.md`, `kaynaklar.md` ve son `analiz/` raporu okunur.
- `davalar/` **git'e gönderilmez** (müvekkil bilgisi). Bu klasördeki hiçbir şeyi commit'leme veya push'lama.

## 6. Repo düzeni
`docs/guncellemeler.md` (son değişiklikler) · `skills/` · `agents/` · `commands/` · `docs/tasarim.md` (tasarım kararları ve kaynak değerlendirmesi) ·
`docs/korpus-dogrulama-raporu.md` · `evals/` (atıf testleri, benchmark indirme) · `araclar/` (Windows kurulum, tez süzme).
Tasarımı değiştiren her karar önce `docs/tasarim.md`'ye yazılır.

## 7. Dil
Kullanıcıyla Türkçe konuş. Analizlerde resmî, günümüz hukuk dili; dilekçelerde `uslup.md`.
