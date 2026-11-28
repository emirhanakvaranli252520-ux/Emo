# Değerlendirme (Eval) Veri Setleri

Sistemin atıf doğruluğunu ve halüsinasyon oranını ölçmek için kullanılır (Aşama 8).
Veriler lisans gereği repoya konmaz; `indir.sh` ile `evals/veri/` altına indirilir.

| Veri seti | İçerik | Lisans | Kullanım |
|---|---|---|---|
| [LawChatAI/turkish-legal-statutory-hallucination-benchmark](https://huggingface.co/datasets/LawChatAI/turkish-legal-statutory-hallucination-benchmark) | 72 somut olay; her olay için kilit unsurlar, **zorunlu** ve **kabul edilebilir** kanun maddeleri (TBK, TCK, TMK, HMK, TTK, İşK, İİK) | CC-BY-NC-4.0 | Somut olaydan doğru maddeye ulaşma ve **uydurma madde** oranı. Atıf: Erdoğanyılmaz, Naç, Çoskuner (SIU 2026) |
| [CtnkyaABC/turkish-law-corpus](https://huggingface.co/datasets/CtnkyaABC/turkish-law-corpus) — `benchmark` | 446 soru; her biri tek bir altın maddeye bağlı (süre, şart, usul, yaptırım, istisna…) | CC-BY-4.0 | Madde bulma isabeti. Atıf: TurkLegalRAG (IEEE UBMK 2026) |

| [Mizan Space](https://huggingface.co/spaces/AlicanKiraz0/Mizan-27B-Turkish-Legal-Decision-Model) — `hard_cases_20` + soru bankası | 20 zor Türk hukuku vakası; beklenen hukuk alanı, temel mevzuat, yargı yolu, talep sonucu, süre sorunu ve gerekçe | CC-BY-NC-4.0 | `/emo:analiz` çıktısının nitelendirme/yargı yolu/süre isabeti. Mizan modelinin kendisi kullanılmaz |

## Ölçülecekler (Aşama 8'de koşturulacak)

1. **Zorunlu madde isabeti:** Sistemin atıf yaptığı maddeler zorunlu maddeleri kapsıyor mu?
2. **Uydurma / alakasız madde oranı:** Kabul edilebilir küme dışındaki atıflar.
3. **Doğrulama disiplini:** Her atıf ✓ / ⚠ ile işaretli mi, ✓ olanlar gerçekten resmî
   kaynaktan mı çekilmiş?
4. **Süre hesabı doğruluğu:** Olaydaki tarihlerden son günün doğru hesaplanması
   (ör. HMK m.20 iki haftalık süre).

## Atıf doğrulayıcı testleri (`vakalar/`)

| Test | Kasıtlı hatalar | Sonuç |
|---|---|---|
| `atif-test-1` | Değiştirilmiş TMK m.6 alıntısı · E/K'si karıştırılmış uydurma künye · kayıt hatası taşıyan tarih | 5/5 doğru (not: cevap anahtarı test sırasında kısa süre erişilebilir durumdaydı) |
| `atif-test-2` (temiz) | HMK m.29'da fıkra kayması · sonucu ters aktarılmış karar · iki gerçek numaradan uydurulmuş HGK künyesi · doğru Yargıtay ve BAM atıfları | 5/5 sorun doğru tespit; doğru atıflarda yanlış alarm yok. Ters aktarılan sonuç anahtarda ⚠, ajanda ✗ idi; tanım ✗ olarak netleştirildi |

Her testte metin (`atif-test-N.md`), cevap anahtarı (`-beklenen.md`) ve ajanın raporu
(`-sonuc.md`) ayrı dosyadır. **Kural:** Cevap anahtarı test bitene kadar repoya konmaz.

## Kullanılmayanlar

- **CtnkyaABC korpusu (106 kanun) ve QA kümesi** bilgi kaynağı olarak kullanılmaz: PDF'ten
  çıkarıldığı için 16.001 satırın ≈2.600'ünde dipnot karışması, kelime bölünmeleri ve kesik
  maddeler tespit edildi. Mevzuat yalnızca resmî kaynaktan alınır.
- **18.305 satırlık soru-cevap dosyası** (kullanıcı yüklemesi, kaynağı belirsiz): cevapların
  yalnızca %3,5'i madde gösteriyor, 270 tekrar soru var, bazı cevaplar aşırı genelleştirilmiş
  veya hatalı. Bilgi kaynağı veya eğitim verisi olarak kullanılmaz.
