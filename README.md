# Emo — Türk Hukuku Uzmanı (Claude Code plugin'i)

Türk hukukunda dava analizi yapan bir Claude Code plugin'i. Her vaka dört bakış açısından
incelenir: **analist**, **karşı taraf avukatı**, **hâkim gözü**, **stratejist**. Ardından
bir **atıf doğrulayıcı**, kullanılan her madde ve karar künyesini Soorgla Türk Hukuku MCP ile
kontrol eder.

**Kapsam:** iş, ceza, aile, tapu ve miras hukuku.
Tasarım kararları için: [`docs/tasarim.md`](docs/tasarim.md)

> Bu araç bir ilk taslak ve analiz yardımcısıdır. Her çıktı avukat kontrolünden geçer.

## Komutlar

| Komut | Ne yapar |
|---|---|
| `/emo:dava-ac <kısa-ad>` | Şablondan dava klasörü açar; belgelerin metnini çıkarır, künye, olay ve kronolojiyi doldurur |
| `/emo:analiz <dava kodu veya olay>` | Dört bakış açılı tam analiz: analist → karşı taraf → hâkim → stratejist → atıf denetimi |
| `/emo:karsi-taraf <dava>` | Hızlı kırmızı takım: karşı tarafın en tehlikeli hamleleri ve hukuka uygun tedbirler |
| `/emo:ictihat <soru>` | Lehe/aleyhe içtihat taraması (arşiv + 11M korpus + güncel resmî kaynak) |
| `/emo:sure <işlem> <tarih>` | Usul süresi hesabı (adli tatil ve resmî tatil kontrolüyle) |
| `/emo:dilekce <tür> [dava]` | Dilekçe taslağı → zorunlu atıf denetimi → antetli UDF |
| `/emo:atif-denetle <dosya>` | Herhangi bir metindeki atıfları resmî kaynaktan denetler (karşı tarafın dilekçesi dahil) |

**Ajanlar:** `analist` (Opus) · `karsi-taraf` (Fable) · `hakim` (Opus) · `stratejist` (Fable) ·
`atif-dogrulayici` (Sonnet; iki temiz testte 10/10)

## Yapı

```
.claude-plugin/
  plugin.json        → plugin kimliği
  marketplace.json   → kurulum kataloğu (bu repo hem plugin hem katalog)
skills/              → uzmanlık modülleri (temel-ilkeler, alan skill'leri, araştırma, dilekçe…)
agents/              → analist, karsi-taraf, hakim, stratejist, atif-dogrulayici
commands/            → /emo:analiz, /emo:dilekce, /emo:sure … kısayolları
scripts/             → UDF okuma ve yardımcı betikler
evals/               → test vakaları
davalar/_sablon/     → yeni dava klasörü şablonu (gerçek davalar git'e gönderilmez)
docs/                → tasarım belgeleri
```

## Kurulum

**Windows (tek tık):** `araclar/KUR-EMO.bat` dosyasını, Emo'nun kurulacağı klasöre (ör. `Masaüstü\Hukuk`)
kopyalayıp çift tıklayın. Git ve Python'u kurar, depoyu indirir, Mütalaa ve arama kütüphanelerini kurar,
isterseniz korpus ve arşivi indirir, `tezler.parquet` varsa hukuk tezlerini süzer ve eklentiyi yükler.

Yerelde deneme (kurulum yapmadan):

```bash
claude --plugin-dir /path/to/Emo
```

GitHub'dan kurulum:

```bash
claude plugin marketplace add emirhanakvaranli252520-ux/Emo
claude plugin install emo@emo-hukuk
```

Resmî kaynak bağlantısı — Mütalaa MCP (zorunlu; mevzuat ve kararları resmî kaynaktan doğrular):

```bash
uv tool install --python 3.12 "https://github.com/hburaktasyurek/MutalaaMCP/releases/download/v0.2.0/mutalaamcp-0.2.0-py3-none-any.whl"
# veya: pip install "mutalaamcp @ git+https://github.com/hburaktasyurek/MutalaaMCP@v0.2.0"
mutalaamcp --help   # kurulum kontrolü; plugin .mcp.json ile otomatik bağlanır
```

Yerel içtihat arşivi (bir kez, ≈5 GB indirme):

```bash
pip install -r skills/ictihat-arsivi/scripts/requirements.txt
python3 skills/ictihat-arsivi/scripts/indir.py
```

İçtihat korpusu (bir kez, ≈5,5 GB; künye ön kontrolü için):

```bash
pip install -r skills/ictihat-korpusu/scripts/requirements.txt
python3 skills/ictihat-korpusu/scripts/korpus.py indir    # HTTPS + SHA-256 doğrulaması
python3 skills/ictihat-korpusu/scripts/korpus.py indeks
```

Doğrulama:

```bash
claude plugin validate .
```

## Durum

- [x] Aşama 1 — Tasarım belgesi
- [x] Aşama 2 — Repo iskeleti ve plugin manifest'i
- [x] Aşama 3 — Temel ilkeler (anayasa) skill'i
- [x] Ek — İçtihat arşivi, Mütalaa (resmî kaynak) bağlantısı, kaynak doğrulama skill'i, eval veri setleri
- [ ] Aşama 4 — MCP bağlantıları (Soorgla araç haritası kaldı)
- [ ] Aşama 5 — Skill'ler
- [x] Aşama 6 — Ajanlar (5)
- [x] Aşama 7 — Komutlar (7)
- [x] İçe aktarma: `/emo:ice-aktar` + `araclar/envanter`
- [ ] Uçtan uca deneme (`/emo:analiz` örnek vaka)
- [ ] Alan skill'leri (iş, ceza, aile, tapu, miras — hile katalogları)
- [ ] Aşama 8 — Eval ve testler
