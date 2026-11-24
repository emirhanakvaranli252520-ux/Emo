# Değerlendirme (Eval) Veri Setleri

Sistemin atıf doğruluğunu ve halüsinasyon oranını ölçmek için kullanılır (Aşama 8).
Veriler lisans gereği repoya konmaz; `indir.sh` ile `evals/veri/` altına indirilir.

| Veri seti | İçerik | Lisans | Kullanım |
|---|---|---|---|
| [LawChatAI/turkish-legal-statutory-hallucination-benchmark](https://huggingface.co/datasets/LawChatAI/turkish-legal-statutory-hallucination-benchmark) | 72 somut olay; her olay için kilit unsurlar, **zorunlu** ve **kabul edilebilir** kanun maddeleri (TBK, TCK, TMK, HMK, TTK, İşK, İİK) | CC-BY-NC-4.0 | Somut olaydan doğru maddeye ulaşma ve **uydurma madde** oranı. Atıf: Erdoğanyılmaz, Naç, Çoskuner (SIU 2026) |
| [CtnkyaABC/turkish-law-corpus](https://huggingface.co/datasets/CtnkyaABC/turkish-law-corpus) — `benchmark` | 446 soru; her biri tek bir altın maddeye bağlı (süre, şart, usul, yaptırım, istisna…) | CC-BY-4.0 | Madde bulma isabeti. Atıf: TurkLegalRAG (IEEE UBMK 2026) |

## Ölçülecekler (Aşama 8'de koşturulacak)

1. **Zorunlu madde isabeti:** Sistemin atıf yaptığı maddeler zorunlu maddeleri kapsıyor mu?
2. **Uydurma / alakasız madde oranı:** Kabul edilebilir küme dışındaki atıflar.
3. **Doğrulama disiplini:** Her atıf ✓ / ⚠ ile işaretli mi, ✓ olanlar gerçekten resmî
   kaynaktan mı çekilmiş?
4. **Süre hesabı doğruluğu:** Olaydaki tarihlerden son günün doğru hesaplanması
   (ör. HMK m.20 iki haftalık süre).

## Kullanılmayanlar

- **CtnkyaABC korpusu (106 kanun) ve QA kümesi** bilgi kaynağı olarak kullanılmaz: PDF'ten
  çıkarıldığı için 16.001 satırın ≈2.600'ünde dipnot karışması, kelime bölünmeleri ve kesik
  maddeler tespit edildi. Mevzuat yalnızca resmî kaynaktan alınır.
- **18.305 satırlık soru-cevap dosyası** (kullanıcı yüklemesi, kaynağı belirsiz): cevapların
  yalnızca %3,5'i madde gösteriyor, 270 tekrar soru var, bazı cevaplar aşırı genelleştirilmiş
  veya hatalı. Bilgi kaynağı veya eğitim verisi olarak kullanılmaz.
