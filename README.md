# Emo — Türk Hukuku Uzmanı (Claude Code plugin'i)

Türk hukukunda dava analizi yapan bir Claude Code plugin'i. Her vaka dört bakış açısından
incelenir: **analist**, **karşı taraf avukatı**, **hâkim gözü**, **stratejist**. Ardından
bir **atıf doğrulayıcı**, kullanılan her madde ve karar künyesini Soorgla Türk Hukuku MCP ile
kontrol eder.

**Kapsam:** iş, ceza, aile, tapu ve miras hukuku.
Tasarım kararları için: [`docs/tasarim.md`](docs/tasarim.md)

> Bu araç bir ilk taslak ve analiz yardımcısıdır. Her çıktı avukat kontrolünden geçer.

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

Yerelde deneme (kurulum yapmadan):

```bash
claude --plugin-dir /path/to/Emo
```

GitHub'dan kurulum:

```bash
claude plugin marketplace add emirhanakvaranli252520-ux/Emo
claude plugin install emo@emo-hukuk
```

Yerel içtihat arşivi (bir kez, ≈5 GB indirme):

```bash
pip install -r skills/ictihat-arsivi/scripts/requirements.txt
python3 skills/ictihat-arsivi/scripts/indir.py
```

Doğrulama:

```bash
claude plugin validate .
```

## Durum

- [x] Aşama 1 — Tasarım belgesi
- [x] Aşama 2 — Repo iskeleti ve plugin manifest'i
- [x] Aşama 3 — Temel ilkeler (anayasa) skill'i
- [ ] Aşama 4 — MCP bağlantıları
- [ ] Aşama 5 — Skill'ler
- [ ] Aşama 6 — Ajanlar
- [ ] Aşama 7 — Komutlar
- [ ] Aşama 8 — Eval ve testler
