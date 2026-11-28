---
description: Bütün davaların yaklaşan süreleri, duruşmaları ve son durumu — günlük/haftalık portföy özeti
argument-hint: [gün sayısı, varsayılan 30]
---

# /emo:durum

1. Çalıştır: `py -3.12 araclar/portfoy/portfoy.py --gun ${ARGUMENTS:-30}` (Linux/Mac: `python3`).
2. Çıktıyı kullanıcıya göster; üstte **⛔ GEÇTİ** ve **🔴 ACİL** (≤7 gün) satırlarını ayrıca vurgula.
3. "Tarihi belirsiz süreler" varsa her biri için: başlangıç olayı biliniyorsa `/emo:sure` ile hesaplamayı öner;
   bilinmiyorsa hangi bilginin (tebliğ tarihi vb.) gerektiğini söyle.
4. "Son güncelleme"si 30 günden eski davaları listele ve gözden geçirilmesini öner.
5. Hiçbir dosyayı değiştirme; bu komut yalnızca rapor verir.
