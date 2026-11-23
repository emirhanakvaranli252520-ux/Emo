# Emo
Türk hukukuna özel yapay zekâ ajanı: dilekçe ve sözleşme taslağı hazırlar, sözleşmeleri madde madde inceleyip riskli hükümleri önem derecesiyle işaretler, mevzuat ve Yargıtay kararı araştırır, süre ve harç hesaplar. Avukatın işini hızlandıran bir ilk taslak aracıdır; her çıktı avukat kontrolünden geçer.

## Day Trader skill paketi (`day-trader/`)

[Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT) paketi bu depoya eklendi ve
geliştirildi. 13 skill, `.claude/skills/` altından bu projede doğrudan `/trader-*` komutu olarak çalışır.

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
python3 -m unittest discover -s day-trader/tests        # 349 test, çevrimdışı
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

Yatırım tavsiyesi değildir. Hiçbir emir kullanıcının açık "evet"i olmadan verilmez; varsayılan kâğıt üzerinde işlemdir (paper trading).
