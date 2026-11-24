# İçtihat Korpusu Doğrulama Raporu

**Tarih:** 24.11.2026 · **Korpus:** `iaiauu/ictihatlar` sürüm `ec10fcae32` (11.045.085 karar)
**Karşılaştırma kaynağı:** Adalet Bakanlığı Bedesten (resmî), Mütalaa MCP aracılığıyla

## 1. Özet

| Soru | Sonuç |
|---|---|
| İndirilen dosyalar bozulmamış mı? | 30/30 dosya SHA-256 ile doğrulandı |
| Karar **metinleri** resmî metinle aynı mı? | **47/47 evet** (rastgele, kaynak ve döneme göre dağıtılmış örneklem) |
| Karar **kayıt bilgisi** (E/K/tarih) güvenilir mi? | **Hayır, her zaman değil** — özellikle UYAP Emsal'de |

**Sonuç:** Korpus, karar **bulmak** ve **metin okumak** için güvenilir. Künye ve tarih ise
**her zaman kararın kendi metninden** alınmalıdır; veritabanı kaydı tek başına kullanılmaz.

## 2. Metin karşılaştırması (47 karar)

| Dilim | Örnek | Sonuç |
|---|---:|---|
| Yargıtay 1997–2005 | 6 | Gövde metni aynı; korpusta yalnızca resmî metnin ilk başlık satırı ("16. Hukuk Dairesi 2004/12499 E., 2004/12335 K.") yok |
| Yargıtay 2006–2015 | 8 | Birebir aynı |
| Yargıtay 2016–2022 | 8 | Birebir aynı |
| Yargıtay 2023–2026 | 8 | Birebir aynı |
| UYAP Emsal (BAM + ilk derece) | 10 | Birebir aynı |
| Danıştay | 6 | Birebir aynı |
| Tarih tutarsızlığı görülen ek kayıt | 1 | Birebir aynı |

Yargıtay ve UYAP Emsal kararlarında korpusun `document_id`'si resmî Bedesten kimliğinin aynısıdır.

## 3. Kayıt bilgisi (metadata) hataları

Kayıttaki tarih ve E/K numarası, kararın **kendi metnindeki** tarih ve numarayla karşılaştırıldı
(kaynak başına 4.000 rastgele karar; metninde tarih/künye bulunanlar üzerinden):

| Kaynak | Tarih metinle aynı | ±1 gün kayma | >1 gün fark | E/K metinde yok |
|---|---:|---:|---:|---:|
| UYAP Emsal | %90,6 | %0,8 | %8,6 | ≈%10 |
| Yargıtay | %98,7 | %0,4 | %0,8 | — |
| Danıştay | %99,8 | — | %0,1 | — |

### Örnek vakalar

| Karar | Korpus kaydı | Resmî sistem kaydı | Kararın kendi metni |
|---|---|---|---|
| İstanbul 16. Asliye Ticaret | T. 03.06.2021 | T. 02.06.2021 | **02/06/2021** |
| Yargıtay 1. HD 2009/859 E. | T. 04.03.2006 | T. 03.03.2006 | **4.3.2009** (iki kayıt da yanlış yıl) |
| İst. Anadolu 1. FSHHM | E. 2016/144, K. 2019/108, T. 02.04.2019 | — | **E. 2018/186, K. 2019/85, T. 28/03/2019** |
| İstanbul 10. Asliye Ticaret | E. 2021/348, K. 2024/855 | — | **E. 2023/539, K. 2024/878** |

Hatanın bir kısmı korpusa değil, **kaynak sistemin kendi kaydına** aittir (1. HD örneğinde
resmî kayıt da yanlış yılı gösteriyor). Bu, yalnızca resmî kayda bakmanın da yetmediğini gösterir.

## 4. Sisteme yansıyan önlemler

1. `kaynak-dogrulama`: Künye ve tarih yalnızca kararın metninden alınır; kayıt ile metin
   çelişirse metin esas alınır ve atıf denetim tablosuna not edilir.
2. `korpus.py oku`: Her kararda **künye-metin kontrolü** (E/K/T ✓/✗) ve ✗ durumunda uyarı.
3. Mahkeme metninde kullanılacak her karar, resmî kaynaktan (`belge_getir`) çekilen metinle
   teyit edilir.

## 5. Yargı Pro ile elle çapraz kontrol listesi

Aşağıdaki künyeleri Yargı Pro'da aratıp "Yargı Pro'da bulundu mu?" ve "Yargı Pro'daki
künye/tarih" sütunlarını doldurun. İlk dört satır, korpusta kayıt hatası tespit edilen
kararlardır; Yargı Pro'nun bunları nasıl gösterdiği, o kaynağın kayıt kalitesini de gösterir.

| # | Mahkeme / Daire | Esas (kayıt) | Karar (kayıt) | Tarih (kayıt) | Yargı Pro'da bulundu mu? | Yargı Pro'daki künye / tarih |
|---|---|---|---|---|---|---|
| 1 | İstanbul 16. Asliye Ticaret Mahkemesi | 2020/285 | 2021/359 | 2021-06-03 | | |
| 2 | İstanbul Anadolu 1. Fikrî ve Sınaî Haklar Hukuk Mahkemesi | 2016/144 | 2019/108 | 2019-04-02 | | |
| 3 | Yargıtay 1. Hukuk Dairesi | 2009/859 | 2009/2671 | 2006-03-04 | | |
| 4 | İstanbul 10. Asliye Ticaret Mahkemesi | 2021/348 | 2024/855 | 2024-12-09 | | |
| 5 | Yargıtay 16. Hukuk Dairesi | 2004/12499 | 2004/12335 | 2004-12-13 | | |
| 6 | Yargıtay 10. Ceza Dairesi | 2003/8772 | 2004/1659 | 2004-02-17 | | |
| 7 | Yargıtay 10. Hukuk Dairesi | 2014/28305 | 2015/3371 | 2015-02-27 | | |
| 8 | Yargıtay 2. Ceza Dairesi | 2015/3401 | 2015/4609 | 2015-03-05 | | |
| 9 | Yargıtay 6. Ceza Dairesi | 2007/20173 | 2011/10882 | 2011-07-06 | | |
| 10 | Yargıtay 8. Hukuk Dairesi | 2014/21456 | 2016/1314 | 2016-01-27 | | |
| 11 | Yargıtay 1. Hukuk Dairesi | 2016/3077 | 2016/2628 | 2016-03-03 | | |
| 12 | Yargıtay 13. Ceza Dairesi | 2015/12091 | 2016/16676 | 2016-12-19 | | |
| 13 | Yargıtay 2. Ceza Dairesi | 2023/18551 | 2023/4465 | 2023-09-14 | | |
| 14 | Yargıtay 2. Ceza Dairesi | 2023/23732 | 2025/24321 | 2025-12-25 | | |
| 15 | İstanbul Anadolu 10. Asliye Ticaret Mahkemesi | 2023/190 | 2023/887 | 2023-11-02 | | |
| 16 | Ankara 11. Asliye Ticaret Mahkemesi | 2022/339 | 2023/684 | 2023-10-20 | | |
| 17 | Bakırköy 7. Asliye Ticaret Mahkemesi | 2021/973 | 2022/130 | 2022-02-09 | | |
| 18 | Danıştay 2. Daire | 2024/4 | 2024/1447 | 2024-03-05 | | |
| 19 | Danıştay İdare Dava Daireleri Kurulu | 2021/1884 | 2022/1283 | 2022-04-07 | | |
| 20 | Danıştay 8. Daire | 2019/3251 | 2020/5789 | 2020-12-17 | | |

Doldurduğunuz tabloyu bana verirseniz sonuçları bu rapora işlerim.
