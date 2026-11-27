---
description: Bilgisayardaki bir klasörü (ör. başka bir hukuk asistanı paketi, eski dosyalar) salt okunur inceler, envanter çıkarır ve işe yarar evrakı Emo'ya sınıflandırarak alır
argument-hint: <klasör yolu>
---

# /emo:ice-aktar

Klasör: $ARGUMENTS

Bu iş **salt okunurdur**: kaynak klasördeki hiçbir dosya silinmez, taşınmaz, değiştirilmez. Yalnızca
kopyalanır. Program dosyaları çalıştırılmaz. Şifreli veya korumalı veriler kırılmaya çalışılmaz.

## 1. Envanter
```
py -3.12 araclar/envanter/envanter.py "<klasör>"
```
(Linux/Mac: `python3`.) Çıktı: `davalar/_ice-aktarma/<tarih>-<klasör>/` → `ENVANTER.md`, `manifest.csv`,
`metin/`, `veritabani/`. PDF'ler için gerekirse `py -3.12 -m pip install pypdf`.

## 2. İncele ve kullanıcıya özetle
`ENVANTER.md`'yi baştan sona oku. Gerekirse `metin/` ve `veritabani/` içindeki dosyaları aç. Kullanıcıya şunu sun:
- Paketin ne olduğu (program mı, veri mi, şablon kütüphanesi mi) ve toplam dosya/tür sayısı
- Aşağıdaki sınıflara göre adetler ve örnekler
- Okunamayan / şifreli / taranmış dosyalar

## 3. Sınıflandır (her dosya için bir sınıf; `manifest.csv`'ye `sinif` sütunu olarak ekle)

| Sınıf | Ne | Nereye | Kural |
|---|---|---|---|
| **A. Dilekçe ve evrak örnekleri / şablonlar** | Dava, cevap, istinaf, temyiz, ihtarname, sözleşme, vekâletname şablonları | `kutuphane/sablonlar/<tür>/` | Kişisel veri içeriyorsa önce anonimleştir (ad → "…", TC no, adres, IBAN silinir). Üslup örneği olarak kullanılabilir; içindeki atıflar **doğrulanmış sayılmaz** |
| **B. Müvekkil / dava verileri** | Dava listesi, duruşma takvimi, dosya belgeleri, müvekkil kayıtları | Her dava için `/emo:dava-ac` ile `davalar/<kod>/` (belgeler → `belgeler/`, metinler → `belgeler-metin/`) | Duruşma ve süre bilgisi varsa `sureler.md`'ye işle ve kullanıcıya ACİL olanları ayrıca listele |
| **C. Mevzuat / içtihat kopyaları** | Kanun metinleri, karar derlemeleri | `kutuphane/kaynak-kopyalari/` | **Kaynak değildir.** Yalnızca bulma amaçlı; her kullanımda Mütalaa ile resmî metinden ✓ yapılır. Kararlar korpus künye kontrolünden geçirilir |
| **D. Hesap tabloları / tarifeler** | Harç, faiz, vekâlet ücreti tabloları | `kutuphane/tablolar/` | Güncelliği yoktur; hesap Soorgla veya resmî tarifeden yapılır |
| **E. Program / sistem dosyaları** | .exe, .dll, kurulum, önbellek | Alınmaz | Yalnızca envanterde kalır |
| **F. Belirsiz** | Ne olduğu anlaşılamayan | Alınmaz | Kullanıcıya sorulur |

## 4. Al
- A, C, D sınıfı dosyaları ilgili `kutuphane/` alt klasörlerine **kopyala**; her alt klasöre `INDEX.md`
  (dosya, tür, kısa açıklama, kaynak yol, SHA-256) yaz.
- B sınıfı için önce kullanıcıya dava listesini göster, **onay alınca** dava klasörlerini aç.
- `davalar/` ve `kutuphane/` git'e **gönderilmez**.

## 5. Rapor
`davalar/_ice-aktarma/<tarih>-<klasör>/RAPOR.md`: alınanlar (sınıf ve hedef yol), alınmayanlar ve sebebi,
okunamayanlar, ACİL süre/duruşma listesi, kullanıcının karar vermesi gerekenler.
