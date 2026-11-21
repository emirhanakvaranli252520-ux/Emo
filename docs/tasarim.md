# Türk Hukuku Uzman Yapay Zekâ — Tasarım Belgesi (Aşama 1)

> Bu belge projenin temelidir. Sonraki bütün dosyalar (CLAUDE.md, skill'ler, ajanlar,
> komutlar) buradaki kararlara dayanır. Karar değişirse önce bu belge güncellenir.

## 1. Amaç

Tek bir avukatın kullanacağı, Claude Code plugin'i olarak çalışan bir hukuk yapay zekâsı:

1. **Derin hukuki analiz:** Olay → nitelendirme → mevzuat → içtihat → ispat.
2. **Karşı tarafı öngörme:** Karşı tarafın başvurabileceği savunmaları, usul hamlelerini
   ve hileli yolları önceden tespit etmek.
3. **Emniyet ve taktik:** Bu hamlelere karşı hukuka uygun koruma tedbirleri ve
   sıralı bir dava stratejisi üretmek.

**Etik sınır:** Sistem karşı tarafın hilelerini tespit eder ve bunlara karşı hukuka uygun
önlem üretir; bizim tarafımız için hileli yol önermez (HMK m.29 dürüstlük ilkesi,
Avukatlık Kanunu meslek kuralları). Hileye dayalı taktik, dosyada aleyhimize döner.

## 2. Kullanım bağlamı

| Konu | Karar |
|---|---|
| Kullanıcı | Tek avukat (sistemin sahibi) |
| Platform | Claude Code plugin'i (skill + ajan + komut + MCP) |
| Gizlilik | Ek kısıt yok; veriler yerel repoda/dava klasörlerinde tutulur |
| Temsil edilen taraf | *Cevap bekleniyor* → **Varsayılan:** her vakada sistem hangi tarafı temsil ettiğimizi sorar |

## 3. Kapsam (ilk sürüm)

| Alan | Alt konular |
|---|---|
| **İş** | İşçilik alacakları (kıdem, ihbar, fazla mesai, UBGT, yıllık izin, ücret), işe iade |
| **Ceza** | Soruşturma (ifade, gözaltı, tutukluluğa itiraz, adli kontrol), kovuşturma, istinaf/temyiz, HAGB, uzlaştırma |
| **Aile** | Çekişmeli boşanma, nafaka (tedbir/iştirak/yoksulluk), velayet ve kişisel ilişki, mal rejimi tasfiyesi |
| **Tapu** | Tapu iptal ve tescil, ortaklığın giderilmesi, el atmanın önlenmesi (men-i müdahale) |
| **Miras** | Tenkis, muris muvazaası |

## 4. Çekirdek mimari: dört bakış açısı

Her vaka analizinde dört alt ajan sırayla çalışır, ardından atıf doğrulayıcı denetler:

```
Vaka + belgeler
   │
   ▼
[0] Bilgi toplama  → eksik bilgi/belge varsa sorulur; yoksa varsayımlar açıkça yazılır
   │
   ▼
[1] ANALİST        → olay özeti, nitelendirme, uygulanacak normlar, ispat yükü, deliller
   │
   ▼
[2] KARŞI TARAF    → karşı tarafın avukatı gibi düşünür: esasa ilişkin savunmalar,
   │                 usul itirazları (görev, yetki, süre, zamanaşımı, arabuluculuk şartı…),
   │                 hileli hamleler (mal kaçırma, muvazaalı devir, tebligat engelleme,
   │                 delil karartma, sahte belge, tanık yönlendirme, davayı uzatma)
   ▼
[3] HÂKİM GÖZÜ     → iki tarafı tarafsız tartar; Yargıtay'ın yerleşik çizgisine göre
   │                 muhtemel sonuç, zayıf noktalar, mahkemenin soracağı sorular
   ▼
[4] STRATEJİST     → emniyet tedbirleri (ihtiyati tedbir, ihtiyati haciz, tapuya şerh,
   │                 delil tespiti, ihtarname, zamanaşımını kesme), taktik sıralama,
   │                 risk matrisi (olasılık × etki), süre takvimi
   ▼
[5] ATIF DOĞRULAYICI → her madde ve karar künyesi Soorgla MCP ile doğrulanır;
                       doğrulanamayan her şey "⚠ DOĞRULANMADI" olarak işaretlenir
```

## 5. Çıktı formatı (karar: C — özet üstte, ayrıntı altta)

```
1. YÖNETİCİ ÖZETİ (en fazla 1 sayfa)
   - Sonuç ve tahmini başarı ihtimali
   - Acil yapılacaklar (süre ve tedbir) — tarihli
   - En büyük 3 risk
2. OLAY VE HUKUKİ NİTELENDİRME
3. UYGULANACAK MEVZUAT (doğrulanmış, olay tarihindeki yürürlük metniyle)
4. İÇTİHAT (lehe ve aleyhe kararlar ayrı)
5. İSPAT VE DELİL DEĞERLENDİRMESİ
6. KARŞI TARAFIN MUHTEMEL HAMLELERİ
7. HÂKİM GÖZÜYLE DEĞERLENDİRME
8. STRATEJİ: emniyet tedbirleri → taktik sıra → risk matrisi → süre takvimi
9. EKSİK BİLGİ / BELGE VE VARSAYIMLAR
10. KAYNAKÇA (doğrulama durumu ile)
```

## 6. Çalışma tarzı (karar: B)

Sistem eldeki bilgiyle **hemen analiz eder**; eksik bilgi ve belgeleri, yaptığı
varsayımları ve bunların sonucu nasıl değiştirebileceğini **sonda listeler**.
İstisna: Temsil edilen taraf belli değilse ve olaydan çıkarılamıyorsa önce bunu sorar.

## 7. Dava hafızası (karar: evet)

```
davalar/
  2026-001-tapu-iptal-tescil/
    dava.md          → taraflar, temsil ettiğimiz taraf, mahkeme, esas no, durum
    olay.md          → olay özeti
    kronoloji.md     → tarihli olay akışı
    belgeler/        → UDF / PDF / DOCX (orijinaller)
    belgeler-metin/  → belgelerin çıkarılmış metinleri
    analiz/          → tarihli analiz raporları
    strateji.md      → güncel strateji ve risk matrisi
    sureler.md       → süre takvimi
    dilekceler/      → üretilen dilekçeler (UDF dahil)
```

Sistem bir davaya döndüğünde önce `dava.md`, `strateji.md` ve `sureler.md` dosyalarını
okuyarak kaldığı yerden devam eder.

## 8. Belge girdileri

| Format | Yöntem |
|---|---|
| **UDF** (birincil) | UDF bir ZIP arşividir; içindeki `content.xml` ayrıştırılarak metin çıkarılır → `scripts/udf_oku.py` |
| PDF | Metin katmanı varsa doğrudan, taranmışsa OCR |
| DOCX | Metin çıkarma |

## 9. İçtihat politikası (karar: evet)

- Her hukuki sorun için **3–5 emsal karar**
- Öncelik: Yargıtay İBK / HGK / CGK → ilgili Daire → BAM → AYM bireysel başvuru → AİHM
- **Aleyhe kararlar da gösterilir** ve bunlardan nasıl ayrışılacağı (distinguishing) yazılır
- Her karar: mahkeme, daire, esas/karar no, tarih, kısa özet, ilgili paragraf, doğrulama durumu

## 10. Dilekçe çıktısı (karar: evet)

Dilekçeler `akvaranli-udf-antet` skill'i ile antetli UDF olarak üretilir.

## 11. Dil ve üslup

**Analiz ve raporlarda:** Resmî, günümüz hukuk dili; net, gerekçeli, terimleri doğru.

**Dilekçelerde** iki şey birlikte gözetilir: Risale-i Nur'daki ifade ahlâkı ve günümüz
hukuk dilinin gereklilikleri.

- **Vakar ve izzet:** Kendinden emin, sakin bir dil. Yalvaran veya öfkeli bir ton yok.
- **İnsaf ve hakkaniyet:** Karşı tarafa hakaret ya da kişisel saldırı yok. Haksızlık
  sıfatlarla değil, delillerle ve akıl yürütmeyle gösterilir.
- **Kelamda iktisat:** Her cümle bir işe yarar. Tekrar, dolgu ve abartı yok.
- **İkna edici muhakeme:** Öncül, delil, sonuç sırası korunur. Yeri geldiğinde açıklayıcı
  bir mukayese veya temsil kullanılabilir.
- **Hakikate bağlılık:** Olaylar çarpıtılmaz. Zayıf nokta varsa gizlenmez, karşılanır.
- **Ölçülü yücelik:** Yer yer seçkin ve ağırbaşlı kelimeler kullanılabilir. Ancak metin
  hâkimin kolayca okuyacağı günümüz Türkçesiyle yazılır, ağır Osmanlıca terkiplere
  yer verilmez.
- **Profesyonellik:** HMK m.119 (dava dilekçesi) ve m.129 (cevap dilekçesi) unsurları
  eksiksiz yer alır. Usul kalıpları (Açıklamalar, Hukuki Sebepler, Deliller, Sonuç ve
  İstem) korunur.

> Kural: Risale-i Nur'dan doğrudan alıntı veya dinî atıf dilekçe metnine konmaz.
> Yalnızca üslup ve ifade ahlâkı örnek alınır.

## 12. Kaynaklar ve araçlar

- **Soorgla Türk Hukuku MCP:** mevzuat, madde geçmişi, içtihat, Resmî Gazete, süre / harç /
  vekâlet ücreti / işçilik alacağı / infaz hesapları, resmî form örnekleri
- **Google Drive MCP** (opsiyonel): arşivden örnek dilekçe

## 13. Bileşen planı

**Ajanlar (`agents/`):** `analist`, `karsi-taraf`, `hakim`, `stratejist`, `atif-dogrulayici`

**Ortak skill'ler (`skills/`):**
`belge-okuma` (UDF/PDF/DOCX), `dava-dosyasi` (hafıza), `mevzuat-arastirma`,
`ictihat-arastirma`, `sure-hesaplama`, `dilekce-yazimi`, `harc-masraf-vekalet`

**Alan skill'leri:** her alanın kendi `references/` klasöründe alt konu rehberi,
**karşı taraf hile kataloğu** ve **emniyet tedbirleri kontrol listesi** bulunur:
`is-hukuku`, `ceza-hukuku`, `aile-hukuku`, `tapu-hukuku`, `miras-hukuku`

**Komutlar (`commands/`):**
`/dava-ac` (yeni dava klasörü), `/analiz` (4 ajanlı tam analiz), `/dilekce`,
`/sure`, `/ictihat`, `/dava-durum`

## 14. Hile kataloğu ilk taslağı (alan skill'lerinde genişletilecek)

> Aşağıdaki madde atıfları taslaktır; alan skill'leri yazılırken Soorgla ile doğrulanacaktır.

| Alan | Karşı tarafın tipik hamlesi | Emniyet / karşı taktik |
|---|---|---|
| İş | Boş kâğıda veya bordroya imza aldırma, şartları taşımayan ibraname, fesih gerekçesini sonradan değiştirme, yanıltıcı SGK çıkış kodu, şirketi boşaltma veya unvan değiştirme | İbranamenin TBK m.420 yönünden denetimi, fesih bildirimine bağlılık ilkesi, delil tespiti, ihtiyati haciz, arabuluculuk ve işe iade sürelerinin takibi |
| Ceza | Kamera kayıtlarının silinmesi, tanığın etkilenmesi, delil karartma, sahte belge | Kayıtların ivedi muhafazası talebi, HTS ve kamera kaydı için erken başvuru, bilirkişi, hukuka aykırı delil itirazı |
| Aile | Boşanma öncesi mal devri veya mal kaçırma, gelir gizleme, çocuğun kaçırılması veya yönlendirilmesi | TMK m.169 geçici önlemler, tapu ve araç kayıtlarına tedbir şerhi, banka/SGK/tapu müzekkereleri, mal rejiminde eklenecek değerler (TMK m.229), pedagog raporu |
| Tapu | Dava sırasında taşınmazı üçüncü kişiye devretme, iyiniyetli üçüncü kişi savunması | Dava açılırken ihtiyati tedbir ve tapuya şerh talebi, kötüniyetin delillendirilmesi |
| Miras | Muvazaalı satış görünümlü bağış, terekeden mal kaçırma, hak düşürücü süre savunması | Muris muvazaası içtihadı (1974 İBK), tedbir şerhi, tereke tespiti, tenkis sürelerinin (TMK m.571) takibi |

## 15. Açık konular

- [ ] **Temsil edilen taraf tercihleri** (Soru 1): cevap gelene kadar sistem her vakada sorar
- [ ] **Kalite referansı** (Soru 9): beğenilen 2–3 dilekçe veya görüş ve sonucu bilinen
      3–5 vaka; Aşama 8'de (eval) istenecek
