# Emo
Türk hukukuna özel yapay zekâ ajanı: dilekçe ve sözleşme taslağı hazırlar, sözleşmeleri madde madde inceleyip riskli hükümleri önem derecesiyle işaretler, mevzuat ve Yargıtay kararı araştırır, süre ve harç hesaplar. Avukatın işini hızlandıran bir ilk taslak aracıdır; her çıktı avukat kontrolünden geçer.

## Day Trader skill paketi (`day-trader/`)

[Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT) paketi bu depoya eklendi ve
geliştirildi. 14 skill, `.claude/skills/` altından bu projede doğrudan `/trader-*` komutu olarak çalışır.

**Eklenen: `/trader-journal` (İşlem Günlüğü).** Orijinal pakette işlem sonrası değerlendirme yoktu. Yeni skill:

- `trader-broker`'ın kaydettiği dolumları (fill) gidiş-dönüş işlemlere çevirir ve her işlemi girişten önce
  yapılan plana göre puanlar (dolar ve **R** cinsinden).
- Kazanma oranı, başabaş kazanma oranı, ortalama kazanç/kayıp, profit factor, beklenen değer (expectancy),
  en büyük düşüş (drawdown), kayıp serileri; strateji, giriş saati ve etikete göre kırılım.
- Disiplin kontrolü: plandan kötü dolan stop, kovalanmış giriş, `flat_by` sonrası çıkış, plansız işlem, geceye taşınan pozisyon.
- Time Machine kalibrasyonu: simülasyonun tahmin ettiği hedef/stop olasılıkları gerçekleşenle karşılaştırılır (Brier skoru).

```bash
python3 day-trader/trader-journal/journal.py snapshot   # planı ve Time Machine olasılıklarını sakla
python3 day-trader/trader-journal/journal.py import     # dolumlar -> puanlanmış işlemler
python3 day-trader/trader-journal/journal.py stats      # karne
python3 -m unittest discover -s day-trader/tests        # 364 test, çevrimdışı
```

**Freqtrade'den uyarlanan fikirler** ([freqtrade/freqtrade](https://github.com/freqtrade/freqtrade), GPLv3: kod kopyalanmadı, yalnızca kavramlar sıfırdan yazıldı):

- `/trader-risk` için isteğe bağlı **protections** (koruma kilitleri), `trader/journal.json`'u okur ve yeni girişleri kilitler;
  çıkışlar asla kilitlenmez. `cooldown` (aynı hisseye N dakika tekrar girme yok), `stop_guard` (son D günde N stop → tüm girişler kapalı),
  `max_drawdown` (son D günde zirveden X$ düşüş → tüm girişler kapalı), `losing_setup` (son N işlemi ortalama F R altında kalan strateji kilitlenir).
- `/trader-journal` karnesine **SQN** (Van Tharp, R üzerinden), **expectancy ratio**, günlük **Sharpe/Sortino** ve
  "bu sonuç şans mı?" sorusu için **t-testi / p-değeri** eklendi.

**Eklenen: `/trader-smc` (Smart Money seviyeleri).** [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts)
(MIT) kütüphanesinin kuralları, pandas/numpy/numba olmadan standart kütüphaneyle yeniden yazıldı:
BOS/CHoCH yapı kırılımları ve trend, fair value gap'ler (açık/dokunulmuş/dolmuş), aktif order block'lar,
eşit tepe/dipler (likidite havuzları, süpürüldü mü) ve önceki günün tepe/dibi. Fiyatın altındaki en yakın destekleri ve
üstündeki dirençleri listeler; `/trader-entry` için giriş seviyesi, `/trader-exit` için stop önerir ve ödül:risk 1'in altındaysa uyarır.
Kütüphanedeki iki **geleceğe bakma (look-ahead)** hatası düzeltildi: swing'ler ancak N mum kapandıktan sonra sayılır,
son muma sahte swing konmaz ve önceden onaylanmış swing'ler sonraki mumlar yüzünden silinmez.

**Eklenen: `/trader-structure` (Advanced Market Structure).** Swing'leri üç katmanda sınıflar:
STH/STL (3 mumluk pivot), ITH/ITL (iki yanında daha düşük STH olan STH; dipler tersi), LTH/LTL (iki yanında daha düşük ITH olan ITH).
Her nokta ancak bilinebildiği mumdan itibaren kullanılır (geleceğe bakmaz). **LTL → daha yüksek ITL → boğa FVG** dizisini
(ve LTH → daha düşük ITH → ayı FVG) H1'de bulur; giriş FVG'nin yakın kenarı, stop ITL/ITH, hedef henüz alınmamış karşı likidite.
Her dizinin sonucunu da izler (hedef, stop, kaçtı, geçersiz). NQ=F, ES=F, BTC/ETH (Binance veya Yahoo) ve BIST; saatler Türkiye saati.
**Range / AMD (PO3) filtresi:** Son 24 mumda verimlilik oranı < 0.3 (fiyat çok yol gidip az ilerliyor), hacim normalin
%80'inin altında (hacim yoksa ATR) ve iki kenar da en az ikişer kez test edilmişse piyasa **range**'dir; kutu dondurulur.
Bir kenarın fitille ya da en fazla 3 mumluk kapanışla alınıp kutuya geri dönülmesi **manipulation**, ardından karşı kenarın
üstünde/altında kapanış **distribution** (AMD tamamlandı). Manipülasyon sonrası okuma: geri dönüş kapanışından giriş, stop
manipülasyon ucunda, hedef karşı kenar ve bir kutu boyu ötesi. `scan` her diziyi oluştuğu rejimle etiketler (`[range]`) ve
sonuçları rejime göre ayırır; `--skip-range` range içindekileri gizler.

```bash
python3 day-trader/trader-structure/structure.py range NQ=F
python3 day-trader/trader-structure/structure.py scan BTCUSDT --source binance --skip-range
```

Henüz yok: alt zaman diliminde konfirmasyon ve key levels (Monday/haftalık/aylık range).

```bash
python3 day-trader/trader-structure/structure.py scan BTCUSDT --source binance
python3 day-trader/trader-structure/structure.py scan NQ=F
```

Yatırım tavsiyesi değildir. Hiçbir emir kullanıcının açık "evet"i olmadan verilmez; varsayılan kâğıt üzerinde işlemdir (paper trading).
