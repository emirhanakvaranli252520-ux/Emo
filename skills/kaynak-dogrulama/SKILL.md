---
name: kaynak-dogrulama
description: Kanun maddesi ve yargı kararlarını resmî kaynaktan (Adalet Bakanlığı Bedesten / mevzuat.gov.tr ve Anayasa Mahkemesi) canlı ve sınırsız doğrulama; mahkemeye sunulacak her metin öncesi atıf denetimi. Bir madde metni, yürürlük, karar künyesi veya alıntı kullanılacağı her durumda; dilekçe, mütalaa veya analiz raporu kesinleşmeden önce yükle.
---

# Kaynak Doğrulama ve Mahkeme Güvenliği

Bu sistemin ürettiği metinler mahkemeye sunulur. Bu nedenle **hiçbir madde metni, karar
künyesi veya alıntı hafızadan yazılmaz.** Hepsi resmî kaynaktan bu oturumda çekilen metne
dayanır.

## 1. Kaynaklar ve öncelik

| Öncelik | Kaynak | Ne için | Sınır |
|---|---|---|---|
| 1 | **Mütalaa MCP** (`mutalaa`) → Bedesten, mevzuat.gov.tr, AYM bilgi bankaları | Mevzuat metni, karar arama ve tam metin, AYM kararları | Yok (resmî servisler, yerel) |
| 2 | **Soorgla MCP** | Madde geçmişi ve sürüm karşılaştırma, Resmî Gazete, **hesaplamalar** (süre, harç, faiz, vekâlet ücreti, işçilik alacağı) | Ücretsiz planda günlük sorgu sınırı |
| 3 | **İçtihat korpusu** (`ictihat-korpusu`, 11 milyon karar) | **Künye ön kontrolü**, ifade araması, AYM ve BAM kararları | Yerel, resmî değil; 2026'ya kadar |
| 4 | **İçtihat arşivi** (`ictihat-arsivi`) | Sınırsız anlamsal emsal **bulma** | 2025 ortasına kadar; yalnızca bulma aracı |
| — | Model bilgisi | Yalnızca nereye bakılacağını tahmin etmek | **Atıf kaynağı değildir** |

## 2. Mütalaa araçları

Araç adları `mcp__plugin_emo_mutalaa__<araç>` biçimindedir. Önce araç açıklamalarını oku;
şemayı hafızadan sabitleme.

| Araç | Kullanım |
|---|---|
| `turk_hukuku_sorularinda_once_bu_araci_cagir` | Araştırma başlangıcı ve yönlendirme |
| `mevzuat_ara` | Kanunu bul: `{"number": "4857", "types": ["KANUN"]}` → `mevzuat:<id>` |
| `mevzuat_madde_getir` | `{"legislation_id": "mevzuat:<id>", "article_number": "20"}` → resmî madde metni + `source_url` + `fetched_at` |
| `mevzuat_icinde_ara` | Bir kanunun içinde ifade arama |
| `mevzuat_madde_agaci_getir` | Kanunun madde ağacı (bölüm/başlık yapısı) |
| `karar_ara` | Karar arama. `courts` **zorunlu**: `yargitay`, `danistay`, `istinaf`, `yerel`. Daire: `chamber` (ör. `H9` = 9. Hukuk Dairesi, `C3` = 3. Ceza Dairesi, `HGK`, `CGK`) |
| `belge_getir` | Kararın resmî tam metni: `{"id": "bedesten:<id>"}` |
| `anayasa_karari_ara` | `kind`: `norm_denetimi` veya `bireysel_basvuru` |

**Arama ipuçları (test edildi):**
- Yan yana yazılan terimler "veya" gibi davranır ve on binlerce sonuç döner. Zorunlu terim
  için `+`, tam ifade için tırnak kullan: `+"muris muvazaası" +"tapu iptal"`.
- Künyesi bilinen kararı bulmak için: `esas_year`, `esas_sequence` (veya `karar_year`,
  `karar_sequence`) + `chamber` + `courts`.
- **Arşivden gelen bir kararın `doc_id`'si resmî kimliğin aynısıdır:** doğrudan
  `belge_getir {"id": "bedesten:<doc_id>"}` ile resmî metni al.
- **`karar_ara` sonucundaki `date` alanı 1 gün erken olabilir** (test: metinde 28.03.2022,
  aramada 2022-03-27). Tarih yalnızca `belge_getir` ile açılan kararın metninden alınır.
- Uzun kararlar sayfalara bölünür: `page.has_more` true ise sonraki sayfaları da çek; tam
  metni okumadan kararın sonucu veya alıntı hakkında hüküm verme.
- Daire filtresi her zaman beklendiği gibi eşleşmeyebilir (ör. `HGK` aramasında HBK kararları
  geldiği görüldü). **Daireyi karar metninin ilk satırından teyit et.**
- Kişi adı, dosya numarası veya müvekkil bilgisi sorguya yazılmaz; sorgu soyut hukuki
  terimlerle kurulur (aracın kendi kuralı da budur).

## 3. Doğrulama kuralları

**Mevzuat (✓ için hepsi gerekli):**
1. Madde metni `mevzuat_madde_getir` (veya Soorgla) ile bu oturumda çekildi.
2. Alıntı, çekilen metinden **kelimesi kelimesine** kopyalandı; kısaltma `(…)` ile gösterildi.
3. Fıkra ve bent numarası metinden sayılarak belirlendi.
4. Madde metnindeki değişiklik / mülga notları okundu. **Olay tarihi, son değişiklik
   tarihinden önceyse** o tarihteki metin Soorgla sürüm araçlarıyla ayrıca kontrol edildi;
   kontrol edilemediyse "olay tarihindeki metin teyit edilmedi" notu düşüldü.
5. Kaynakçaya `source_url` ve çekiliş tarihi yazıldı.

**İçtihat (✓ için hepsi gerekli):**
1. Karar `belge_getir` ile resmî kaynaktan çekildi.
2. Künye **metnin kendisinden** alındı: mahkeme, daire, E., K., karar tarihi.
   Arama sonuçlarındaki ve veritabanlarındaki kayıt bilgisi (metadata) künye kaynağı
   **değildir**: testte UYAP Emsal kayıtlarının ≈%10'unda E/K, ≈%9'unda tarih kararın kendi
   metniyle uyuşmadı; Yargıtay'da tarih uyuşmazlığı ≈%1,3; resmî sistemin kendi kaydında da
   yıl hatası görüldü. Tarih; başlıktaki "KARAR TARİHİ" satırından veya sondaki
   "… tarihinde oybirliğiyle/oyçokluğuyla karar verildi" cümlesinden alınır. Kayıt ile metin
   çelişirse **metin esas alınır** ve çelişki denetim tablosuna not edilir.
3. Kararın **sonucu** (onama / bozma / kaldırma; kimin lehine) metinden okundu.
4. Kullanılan ilke veya alıntı metinde birebir var; alıntı tırnak içinde ve kelimesi kelimesine.
5. Kararın konusu ve olgu yapısı bizim olayla karşılaştırıldı (benzerlik/farklılık yazıldı).
6. **Bozma kararlarında** dikkat: bozma gerekçesi bir ilkeyi her zaman genel olarak
   koymaz; bazen yalnızca eksik inceleme tespitidir. Bu ayrım rapora yazılır.

## 4. Mahkemeye sunulacak metinlerde atıf denetimi

Dilekçe, cevap, istinaf/temyiz dilekçesi veya mütalaa **kesinleşmeden önce** şu denetim yapılır:

1. Metindeki **bütün** kanun ve karar atıflarını listele.
2. **Künye ön kontrolü:** Her karar künyesini önce `ictihat-korpusu` ile ara
   (`korpus.py --json kunye --esas … --karar … --daire …`). Korpusta bulunamayan künye
   uydurma şüphelisidir; resmî kaynakta da bulunamazsa metinden çıkarılır.
   Yargıtay kararlarında korpus `document_id`'si resmî Bedesten kimliğinin aynısıdır:
   `belge_getir {"id": "bedesten:<document_id>"}`.
3. Her biri için §3'teki kontrolleri yap. "✓ arşiv" veya "⚠" durumundaki her atıf **resmî
   kaynaktan yeniden teyit edilir**; mahkeme metninde yalnızca resmî kaynaktan doğrulanmış
   (✓) atıf kalabilir.
4. Teyit edilemeyen atıf **metinden çıkarılır** veya avukata açıkça sorulur. Mahkeme
   metnine ⚠ işareti konmaz; ⚠'li atıf, metne hiç girmez.
5. Her alıntıyı kaynak metinle karakter karakter karşılaştır.
6. Denetim sonucunu dilekçenin yanında ayrı bir **atıf denetim tablosu** olarak ver:

| # | Atıf (metindeki hali) | Kaynak | Durum | Not |
|---|---|---|---|---|
| 1 | Yargıtay 9. HD, E. 2022/2530, K. 2022/4045, T. 28.03.2022 | mevzuat.adalet.gov.tr/ictihat/759068100 | ✓ | Sonuç: onama, işçi lehine |

## 5. Bilinen halüsinasyon tuzakları (her seferinde kontrol et)

- **Madde numarası kayması:** Doğru kanun, yanlış madde veya yanlış fıkra/bent.
- **Mülga veya değişmiş hüküm:** Madde kaldırılmış, yeniden düzenlenmiş veya AYM tarafından
  iptal edilmiş olabilir. Metindeki notları oku.
- **Kanun karışması:** Benzer konudaki iki kanunun maddeleri (ör. 1475 / 4857 sayılı İş
  Kanunları; 818 / 6098 sayılı Borçlar Kanunları; 765 / 5237 sayılı TCK) birbirine karışır.
- **Uydurma künye:** Gerçekçi görünen ama var olmayan E./K. numarası. Künye ancak
  `belge_getir` ile açılan metinden yazılır.
- **"Bilinen" ama yanlış hukuk kuralları:** Ör. "ihtarname zamanaşımını keser" — **yanlış**; TBK m.154
  zamanaşımını kesen sebepleri sınırlı sayar (ikrar, dava/def'i, hakeme başvuru, icra takibi, iflas masasına
  başvuru). İhtarname, muaccel borçta temerrüt sonucu doğurur (TBK m.117). Usul ve süre sonuçları
  doğuran her kural, model "bildiğini" düşünse bile madde metninden doğrulanır.
- **Hatalı kayıt bilgisi:** Gerçek bir kararın veritabanı kaydı başka bir dosyanın
  numarasını veya bir gün kaymış tarihi taşıyabilir. Künye ve tarih yalnızca metinden alınır.
- **Daire görev değişikliği:** Bir konuya bakan daire yıllar içinde değişti; eski bir daire
  kararı güncel çizgiyi yansıtmayabilir. Karar tarihini ve güncel kararları kontrol et.
- **İBK künyeleri ve tarihleri:** Özellikle sık atıf yapılan İBK'larda tarih ve numara
  resmî metinden alınır.
- **Sonucun ters okunması:** Karşı oy veya bozulan ilk derece gerekçesi, kararın
  kendisiymiş gibi alıntılanmamalı.

## 6. Kaynak erişilemezse

- Mütalaa bağlı değilse: `mutalaamcp` kurulumu için README'ye yönlendir, Soorgla ile devam et.
- Her ikisi de yoksa: Analiz yapılabilir ama atıflar ⚠ kalır. **Mahkemeye sunulacak metin
  üretilmez**; avukata, teyit edilmesi gereken atıfların listesi verilir.
- Bir araç hata verirse hata açıkça söylenir; başka bir kaynaktan alınan bilgi resmî
  kaynaktan doğrulanmış gibi sunulmaz.
