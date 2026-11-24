---
description: Dört bakış açılı tam dava analizi (analist → karşı taraf → hâkim → stratejist → atıf doğrulayıcı)
argument-hint: <dava klasörü kodu veya olay metni>
---

# /emo:analiz

Girdi: $ARGUMENTS

Önce `temel-ilkeler` skill'ini yükle ve uygula.

## 0. Hazırlık
1. Girdi `davalar/` altında bir klasör koduysa o klasörü kullan; değilse girdiyi olay metni say.
   Olay metniyse ve kullanıcı açık bir dava kodu vermediyse, analizi `davalar/_gecici-<YYYY-AA-GG>/`
   altına kaydet ve sonunda `/emo:dava-ac` ile kalıcı klasör açmayı öner.
2. Dava klasöründe `dava.md`, `olay.md`, `kronoloji.md`, `strateji.md`, `sureler.md`,
   `kaynaklar.md` ve son analiz raporunu oku. `belgeler/` içinde metni çıkarılmamış belge
   varsa metnini çıkarıp `belgeler-metin/` altına kaydet.
3. **Temsil ettiğimiz taraf** belli değilse ve olaydan anlaşılmıyorsa yalnızca bunu sor ve dur.
4. Çalışma klasörü: `analiz/_calisma/<YYYY-AA-GG>/`.

## 1–4. Dört bakış açısı (sırayla, her biri bir öncekinin çıktısını okur)
Her adımda Agent aracıyla ilgili eklenti ajanını çağır (`emo:<ad>`; görünmüyorsa `<ad>`).
Ajana dava klasörünün yolunu, temsil ettiğimiz tarafı, önceki çıktı dosyalarının yollarını ve
kendi çıktısını yazacağı dosya yolunu ver.

| Sıra | Ajan | Çıktı dosyası |
|---|---|---|
| 1 | `analist` | `_calisma/<tarih>/1-analist.md` |
| 2 | `karsi-taraf` | `_calisma/<tarih>/2-karsi-taraf.md` |
| 3 | `hakim` | `_calisma/<tarih>/3-hakim.md` |
| 4 | `stratejist` | `_calisma/<tarih>/4-stratejist.md` |

Bir ajan hata verirse aynı ajanı bir kez daha çağır; yine başarısız olursa eksik bölümü
raporda açıkça belirt ve devam et.

## 5. Raporu birleştir
`temel-ilkeler/references/cikti-formati.md` şablonuna göre dört çıktıyı tek rapor halinde
`analiz/<YYYY-AA-GG>-<konu>.md` dosyasına yaz: Yönetici özeti (stratejist) en üstte, ardından
2–6 (analist), 7 (karşı taraf), 8 (hâkim), 9–10 (stratejist), 11 kaynakça.

## 6. Atıf denetimi
`atif-dogrulayici` ajanını birleştirilmiş rapor üzerinde çalıştır. Denetim tablosunu raporun
sonuna "Atıf Denetimi" başlığıyla ekle. ✗ olan atıfları rapordan çıkar veya düzelt; ⚠
olanların işaretini rapora işle. Değişiklik yaptıysan denetimi değişen atıflar için tekrarla.

## 7. Dava hafızasını güncelle
- `strateji.md` ← 9.1–9.3 · `sureler.md` ← 9.4 · `kaynaklar.md` ← ✓ atıflar ·
  `dava.md` → "Son durum" ve "Son güncelleme".

## 8. Kullanıcıya yanıt
Yalnızca şunları yaz: yönetici özeti, ACİL tablosu, en büyük 3 risk, atıf denetimi özeti
(✓/⚠/✗ sayıları) ve raporun dosya yolu.
