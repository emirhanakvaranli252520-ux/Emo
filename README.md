# Emo
Türk hukukuna özel yapay zekâ ajanı: dilekçe ve sözleşme taslağı hazırlar, sözleşmeleri madde madde inceleyip riskli hükümleri önem derecesiyle işaretler, mevzuat ve Yargıtay kararı araştırır, süre ve harç hesaplar. Avukatın işini hızlandıran bir ilk taslak aracıdır; her çıktı avukat kontrolünden geçer.

## Day Trader skill paketi (`day-trader/`)

[Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT) paketi bu depoya eklendi ve
geliştirildi. 15 skill, `.claude/skills/` altından bu projede doğrudan `/trader-*` komutu olarak çalışır.

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
python3 -m unittest discover -s day-trader/tests        # 399 test, çevrimdışı
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

**Key levels:** gün/hafta/ay açılışları (DO/WO/MO), önceki gün/hafta/ayın tepe-dip-orta seviyesi (PDH/PDL/PDEQ,
PWH/PWL/PWEQ, PMH/PML/PMEQ), Monday range (MH/ML/MEQ) ve NQ/ES için New York gece yarısı açılışı (MNO). Her tepe/dip
için alınıp alınmadığı, ne zaman ve nasıl (süpürüldü mü, kabul mü gördü), Monday range'de önce hangi tarafın alındığı ve
fiyatın bu range'lerde premium mu discount mu olduğu. Periyot sınırları piyasaya göre: kripto 00:00 UTC (TR 03:00) ve
Pazartesi, CME vadelileri New York 18:00 ve Pazar akşamı, ABD hisseleri New York günü, BIST İstanbul günü.

```bash
python3 day-trader/trader-structure/structure.py levels BTCUSDT --source binance
python3 day-trader/trader-structure/structure.py levels NQ=F
```

**STH/STL = yakıt (likidite):** `scan` her grafikte STH/STL/ITH/ITL'lerin yüzde kaçının 6/12/24/48 mum içinde alındığını,
medyan alınma süresini ve fiyata en yakın alınmamış olanları gösterir. Dürüst test için **taban oranı** da verir:
aynı uzaklıktaki herhangi bir seviye 24 mumda ne sıklıkla alınıyor? Her dizinin planına en yakın alınmamış STH/STL
**ilk hedef (T1)** olarak eklenir; stopun hemen ötesinde alınmamış STL/STH varsa "stop likiditenin içinde" uyarısı çıkar.

**R:R bandı 1:1.5 – 1:3.5:** `trader-structure` planlarında ve Elliott sayımlarında bandın dışındaki R:R işaretlenir
(`--rr-min/--rr-max` ile değişir). `trader-risk` için `trader/config.json`'a `"min_reward_risk": 1.5` (altını engeller) ve
`"max_reward_risk": 3.5` (üstünü uyarır, kısmi kâr önerir) yazılabilir.

**Eklenen: `/trader-elliott` (Elliott Wave).** ATR zigzag ile üç derecede swing bulur; dalga 2/B, 3, 4, 5, impulse tamamlandı,
zigzag/flat C ve ending diagonal sayımlarını iki yönde dener. Kesin kurallardan birini çiğneyen sayımı atar (dalga 2 dalga 1'in
başını geçemez, dalga 3 en kısa olamaz, dalga 4 dalga 1 bölgesine giremez, flat'te B, A'nın %90-138.2'si), kalanları kılavuzlara
göre puanlar (Fibonacci oranları, alternation, hacim). Sayımlar aynı yönde birleşirse yön + geçersizlik seviyesi (doğal stop) +
hedef verir; birleşmezse "Elliott burada karar vermiyor" der. `evaluate` geçmişte, yalnızca o an bilinen veriyle sayım yapıp
yön tahminlerini taban oranla karşılaştırır. `reference.md` kuralları, kılavuzları ve akademik kanıtları özetler.

```bash
python3 day-trader/trader-elliott/elliott.py count BTCUSDT --source binance
python3 day-trader/trader-elliott/elliott.py evaluate NQ=F --horizon 48
```

**Alt zaman diliminde konfirmasyon:** `confirm`, M5 verisinden H1 mumları kurar, LTL→ITL→FVG bölgelerini bulur ve her birini
M5'te izler: bölgeye dokunuş → bölgede yapılan dibin öncesindeki son M5 ara tepesinin üstünde kapanış (CHoCH) → giriş CHoCH
kapanışı, stop bölgedeki M5 dibi (isteğe bağlı ATR tamponu), hedef H1 hedefi. R:R bandınız uygulanır (1.5 altı atlanır, 3.5
üstünde 3.5R'de kâr alınır). Aynı bölgelerde **H1'den doğrudan girmek** ile **M5 CHoCH beklemek** karşılaştırılır. `--zone`
ile kendi bölgenizi (key level, order block, range kenarı) izletebilirsiniz.

**Hacimli piyasa kalıbı:** H1 hacmi normalin en az 1.2 katıyken LTL beklenmez; ITL → STH ve bu bacakta bırakılan FVG
bölge olur (ayıda ITH → STL). `--pattern both|classic|fast`, eşik `--fast-vol`. Sonuçlar kalıba göre ayrılır.

**TradingView verisi:** Grafikte "Export chart data" ile alınan CSV (time, open, high, low, close, Volume) tüm komutlarda
`--offline dosya.csv` ile okunur; günlük bias için ayrıca `--bias-offline gunluk.csv`.

```bash
python3 day-trader/trader-structure/structure.py confirm BTCUSDT --offline btc_15m.csv --bias-offline btc_1d.csv
python3 day-trader/trader-structure/structure.py confirm NQ --offline nq_5m.csv --data-interval 5m --bias-offline nq_1d.csv
```

Varsayılan konfirmasyon **15m ITL/ITH**: FVG'ye dokunuştan sonra 15m'de oluşan ilk ITL (long) / ITH (short) kesinleşince
giriş, stop ITL dibinde (CHoCH isteğe bağlı: `--mode choch`). H1 range kutusu içinde oluşan kurulumlar karşılaştırmaya
alınmaz (`--include-range` ile alınır). Fiyat FVG'ye dönmeden H1 hedefine gittiyse kurulum "kaçtı" sayılır.

Varsayılan zincir **1D bias → 1H bölge → 15m konfirmasyon**: her bölge o andaki günlük yapıyla (son iki günlük ITH/ITL,
yoksa STH/STL; yalnızca kapanmış günlük mumlar) etiketlenir ve sonuçlar "bias ile aynı yönde" ve "karşı/belirsiz" diye ayrılır.

```bash
python3 day-trader/trader-structure/structure.py confirm NQ=F
python3 day-trader/trader-structure/structure.py confirm BTCUSDT --source binance --days 30
python3 day-trader/trader-structure/structure.py confirm NQ=F --ltf 5m --bias-tf none   # eski H1 -> M5
```

```bash
python3 day-trader/trader-structure/structure.py scan BTCUSDT --source binance
python3 day-trader/trader-structure/structure.py scan NQ=F
```

Yatırım tavsiyesi değildir. Hiçbir emir kullanıcının açık "evet"i olmadan verilmez; varsayılan kâğıt üzerinde işlemdir (paper trading).
