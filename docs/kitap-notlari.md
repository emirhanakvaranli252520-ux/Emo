# Kitap notları: işlem ve yatırım skill'leri için

Kullanıcının paylaştığı dört kaynaktan çıkarılan, araçlara dönüştürülebilir dersler.
Özetler kendi cümlelerimizledir; kitaplardan uzun alıntı yoktur. Her ders, hangi skill'de
nasıl kullanılabileceğiyle birlikte yazıldı.

Okunanlar:
- **Alfa Crypto Ders Notları** (27 sayfa): tamamı (grafik görselleri metin olarak okunamadı).
- **Akıllı Borsacı, Kırşat Keskin** (67 sayfa): tamamı (sondaki terimler sözlüğü hariç).
- **Alfa Trader, Brent Donnelly** (488 sayfa): içindekiler, 11. bölüm (veri, risk yönetimi,
  varyans, pozisyon büyüklüğü) tam; 6, 8, 12, 15. bölümler başlık düzeyinde; Ek B tam.
- **Akıllı Yatırımcı, Benjamin Graham** (635 sayfa): içindekiler, 14. bölüm (savunmacı
  yatırımcının 7 kriteri), 20. bölüm (güvenlik marjı) girişi, 8. bölüm (Bay Piyasa) ana fikri.

---

## 1. Alfa Crypto Ders Notları: kurallı formasyonlar

Ana fikir: formasyon kuralsız kullanılırsa kaybettirir. Formasyon tek başına "odun"dur;
üst zaman dilimi yapısı, trend yönü, önemli bölgeler ve bir gösterge ile birleşince "ev" olur.
5-10 işlemlik kayıp serisiyle yöntem terk edilmez: yüzlerce işlemlik backtest gerekir.

Her işlem için **CEST**: Conditions (koşullar), Entry (giriş), Stoploss, Target.

Formasyon kuralları (ölçülebilir hale getirilmiş):

| formasyon | kural |
| --- | --- |
| ikili dip / tepe | ilk dibin (tepenin) **gövde ucu ile fitil ucu arası** bir kutu; ikinci dipte fitil kutuyu geçebilir ama **gövde kapanışı kutunun dışına taşmaz** (taşarsa formasyon bozulur). İkinci dip, birinciden sonra yaklaşık **5 ile 25 mum** arasında gelir. Kutuyu fitille aşıp geri kapanmak likidite alımı sayılır |
| OBO (tepe) | yeni HH sonrası geri çekilmenin dibi (gövde ve fitil) boyun bölgesi; baş oluşurken fiyat boyuna dokunur ama gövde ile altında kapanmaz; sağ omuz **"termination zone"**dan döner: sol omuzun en yüksek gövdesi ile başın en yüksek gövdesi arası; sağ omuz başın gövde ucunu aşarsa formasyon bozulur; boyun **hacimli mumla** kırılır |
| TOBO (dip) | aynısının aynası |
| koşul | OBO/ikili tepede **RSI 70 üstü**, TOBO/ikili dipte **RSI 30 altı** (baş bölgesinde) |
| giriş | boyuna son test veren mumun gövde ucunu kıran ilk kapanış (agresif) ya da kırılım sonrası retest |
| stop | boyun / son seviye ötesi **+ 1 ATR** |
| hedef | notlarda **1.4R** (kullanıcının bandı 1.5-3.5R) |
| trend devamı | **EMA 200** üstünde ikili dip / TOBO (long), altında ikili tepe (short); stop ikili dibin son ucu ya da başın ucu |

Kullanım: `/trader-smc` veya yeni bir formasyon tarayıcısı bu kuralları kodlayıp
`/trader-structure confirm` gibi geçmiş veride test edebilir. Notların kendi uyarısı: "her
koşul oluşsa da stop olabilirsiniz", bu yüzden kararı tek örnek değil istatistik verir.

## 2. Akıllı Borsacı: BIST temel analiz eşikleri

Başlangıç seviyesinde bir kitap; işe yarar kısmı Türkiye'ye özgü pratik eşikler:

- Esas faaliyet kârının net kâr içindeki payı yüksek olmalı (arsa satışı gibi tek seferlik
  kâra dikkat; kitap %80 altını uyarı sayıyor).
- Satış ve kâr büyümesi **enflasyonun üzerinde** olmalı (nominal büyüme yanıltır).
- Özsermaye kârlılığı yüksek (kitap %25-30 üstü diyor), cari oran 1.5 üstü,
  toplam borç / toplam varlık %50-60 altı.
- F/K'yı sektör ortalamasıyla ve esas faaliyet kârıyla birlikte oku.
- Yönetim kalitesi: hisse yükselirken sürekli bedelli / pay satışı yapan patron risklidir.
- Takas analizi: yabancı payı artan hisseler; tek başına değil, aracı kurum dağılımıyla.
- Düşen trendde, trend dönmeden alım yapma.
- İhracat payı yüksek şirketler kur şoklarına daha dayanıklı.
- Yatırılan para en az 3 yıl ihtiyaç duyulmayacak para olmalı.

## 3. Alfa Trader (Brent Donnelly): risk, varyans, süreç

**Veri önce gelir.** Günlük K&Z tablosu tut: tarih, stop, açılış, gün içi en yüksek, en düşük,
kapanış; strateji ve ürün başına sütun; 15 sütunu geçme. Yaklaşık 6 ay sonra hesapla:
- **Kazanma oranı** ve **ortalama kazanç / ortalama kayıp**. Donnelly'ye göre beceriyi en iyi
  ikincisi gösterir; kazanma oranı daha çok tarzdan gelir.
- Stop'u kaç kez aştın ve neden (aşıldıysa süreç bozuktur).
- **Haftanın gününe ve günün saatine göre K&Z**: para nerede ve ne zaman kaybediliyor? Kârlı
  saatlerde odaklan, kârsız saatlerde işlem yapma.

**Risk yönetimi katmanları:**
- **Yıllık**: yıla yavaş başla, kâr biriktikçe risk artır ("call opsiyonu gibi ol": kötü
  yıllar küçük kayıp, iyi yıllar büyük kazanç). Gerçekçi oran: yıllık hedef / yıllık maksimum
  kayıp yaklaşık 2.5.
- **Metagame**: çalıştığın yerin gerçek kuralları (prop firm için: günlük ve toplam drawdown,
  tutarlılık kuralı) resmi stop'tan daha belirleyicidir.
- **Aylık**: her ay başında aylık stop, aylık hedef, işlem tiplerine ayrılan risk ve bir kişisel
  hedef (uyku, spor).
- **Günlük**: yeni başlayan kısa vadeli trader için en basit sistem: her sabah serbest
  sermayenin **%1**'ini riske et, fazlasını değil.
- **İşlem tipleri**:
  - Tip I (rutin): serbest sermayenin %1-3'ü (yeniysen %1).
  - Tip II (anlatı değişimi, yüksek inanç): %3-5, iyi bir yılda üstüne YTD kârın %10'u.
  - Tip III (nadir, dönüm noktası): yalnızca güçlü konumdayken, parametreler içinde en büyük risk.
- **Pozisyon büyüklüğü bir çıktıdır**: önce risk edilecek tutar, sonra piyasaya göre stop,
  sonra boyut = risk / (giriş - stop). Stop'u "kaybetmeyi göze aldığım tutara" göre koymak
  yanlıştır. Stop en az ortalama aralık kadar uzakta olmalı, yoksa gürültüde patlar.
- Birden çok pozisyon aynı yönde ise tek bir risk bloğu say.

**Varyans mı, kötü süreç mi?** Yanılmak ve şanssızlık varyanstır. Ama şunlar varyans değildir:
piyasayı doğru okuyup yine de kaybetmek, plansız işlem, aşırı işlem, stop'u kaydırmak,
kaybedeni büyütmek, rejim değişimine uyum sağlayamamak, stres, yorgunluk. Bunlar varsa riski kes.
%50 kazanma oranında 6-7 günlük kayıp serisi normaldir.

**Kaybedenlerin 13 özelliği** (kısaltılmış): aşırı işlem, avantaj yok, yanılmaktan nefret,
aşırı özgüven, tetiği çekememek, basit göstergelere aşırı güven, risk yerine fikir düşünmek,
her işlemde aynı boyut, dürtüsellik, sezgisel (Sistem 1) düşünme, az okuma, kendine yalan,
kumar.

## 4. Akıllı Yatırımcı (Graham): değer ve güvenlik marjı

**Bay Piyasa**: piyasa her gün fiyat teklif eden duygusal bir ortaktır; fiyatı bilgi olarak
kullan, emir olarak değil. Coşkuda satın alma, panikte satma.

**Savunmacı yatırımcının 7 kriteri:**
1. Yeterli büyüklük (küçük, dalgalı şirketleri dışarıda bırak).
2. Güçlü finansal durum: cari oran en az 2; uzun vadeli borç net işletme sermayesini aşmasın.
3. Kazanç istikrarı: son 10 yılın her birinde kâr.
4. Temettü geçmişi: uzun ve kesintisiz.
5. Kazanç büyümesi: 10 yılda hisse başı kâr en az üçte bir artmış (3 yıllık ortalamalarla).
6. Makul F/K: fiyat, son 3 yılın ortalama kârının en fazla 15 katı.
7. Makul PD/DD: en fazla 1.5; ya da **F/K x PD/DD 22.5'i geçmesin**.

**Güvenlik marjı**: geleceği tam tahmin edemediğimiz için, fiyat ile değer arasında hatalara
dayanacak bir yastık ararız. Hisse için ölçü: **kâr getirisi (1/F/K), tahvil faizinin belirgin
üzerinde** olmalı.

**Türkiye'ye uyarlarken dikkat:**
- Kriterlerdeki dolar tutarları ve "10 yıl kâr" testi, yüksek enflasyon ve 2023'ten beri
  uygulanan enflasyon muhasebesi (TMS 29) nedeniyle doğrudan uygulanamaz: reel (enflasyona
  göre düzeltilmiş) rakamlar ve dolar bazlı kâr kullanılmalı.
- Güvenlik marjı testi Türkiye'de çok sert: politika faizi %36 iken, kâr getirisinin tahvil
  faizini geçmesi için F/K yaklaşık 3'ün altında olmalı. Bu nominal karşılaştırma yanıltıcı
  olabilir; reel faiz ve reel kâr büyümesiyle düşünmek gerekir.
- Katılım endeksi filtresi (faiz geliri ve faizli borç sınırları) Graham'ın borç kriterleriyle
  doğal olarak uyumludur.

---

## Skill'lere aktarım listesi

| ders | nereye | durum |
| --- | --- | --- |
| günün saati / haftanın günü K&Z, kazanç/kayıp oranı | `/trader-journal` | saat var, gün eklenecek |
| %1 günlük risk, Tip I/II/III risk, YTD'ye göre risk ölçekleme, aylık stop | `/trader-risk`, `/trader-budget` | eklenecek |
| "varyans mı süreç mi" kontrol listesi | `/trader-journal` stats yorumu | eklenecek |
| stop en az bir ortalama aralık / ATR | `/trader-exit`, `confirm` (`--buffer`) | kısmen var |
| ikili dip-tepe, OBO/TOBO kuralları, RSI + EMA200 koşulları | yeni formasyon tarayıcısı + backtest | eklenecek |
| Graham 7 kriter + F/K x PD/DD <= 22.5, Keskin eşikleri | BIST temel analiz tarayıcısı | eklenecek (veri gerekli) |
