# SARLO_UZ Telegram Bot

Bu bot Xweardan olingan mahsulot e'lonlarini avtomatik ravishda **SARLO_UZ**
do'koni formatiga qayta formatlaydi:

- 💰 Narxdan har doim **1 000 so'm** ayiradi (doimiy narx qo'ymaydi)
- 🏷️ `LOOK:` qatorini har doim `SARLO_UZ` qiladi
- 👤 Buyurtma username'ini `@sarlo_admin` ga o'zgartiradi
- 🗑️ `Отзыв:` (review) qatorini butunlay olib tashlaydi
- 🇺🇿 Pastiga tabiiy o'zbekcha tarjimasini qo'shadi
- 🖼️ Rasm + caption yuborilsa — rasmni saqlab, faqat caption'ni qayta yozadi
- ♻️ Forward qilingan Xwear postlarini ham qayta ishlaydi

AI API ishlatilmaydi — narxni aniqlash va tarjima oddiy Python regex va
lug'at asosida ishlaydi.

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `bot.py` | Botning asosiy kodi (aiogram 3.x, long polling) |
| `requirements.txt` | Python kutubxonalari |
| `render.yaml` | Render.com uchun tayyor konfiguratsiya |
| `.env.example` | `BOT_TOKEN` uchun namuna |
| `.gitignore` | `.env` va vaqtinchalik fayllarni git'ga qo'shmaslik |

## Narx qoidasi

Har qanday holatda ham asosiy mahsulot narxidan **1000 so'm** ayiriladi
(cargo/kargo narxi bunga kirmaydi). Masalan:

```
400.000 → 399.000
500.000 → 499.000
1.000.000 → 999.000
```

Narx `400k`, `400 000`, `400000` kabi turli formatlarda yozilgan bo'lsa ham
bot uni aniqlashga harakat qiladi. `$` bilan yozilgan narxlar (masalan `$50`)
dollar hisoblanadi va so'mdagi kabi avtomatik ayirilmaydi — bularni botning
javobida qo'lda tekshirib ko'ring.

## Bosqichma-bosqich: Telefondan GitHub + Render orqali deploy qilish

Buni to'liq telefondan, kompyutersiz bajarish mumkin.

### 1-qadam: Telegram bot yaratish (agar hali yaratmagan bo'lsangiz)

1. Telegram'da **@BotFather** ga o'ting.
2. `/newbot` buyrug'ini yuboring va bot nomi/username'ini kiriting.
3. BotFather sizga **BOT_TOKEN** beradi (masalan `123456789:AAExample...`).
   Uni saqlab qo'ying — keyinroq kerak bo'ladi.

### 2-qadam: Kodni GitHub'ga yuklash

1. Telefoningizga **GitHub** ilovasini (yoki brauzerdan github.com) oching,
   hisobingizga kiring.
2. Yangi repository (masalan `sarlo-uz-bot`) yarating — **Private** qilib
   qo'yish tavsiya etiladi (BOT_TOKEN sizib chiqmasligi uchun).
3. Ushbu suhbatda yuklab olingan barcha fayllarni (`bot.py`,
   `requirements.txt`, `render.yaml`, `.env.example`, `.gitignore`,
   `README.md`) repositoryga yuklang:
   - GitHub mobil ilovasida repository ochib, **"Add file" → "Upload
     files"** orqali fayllarni birma-bir yoki hammasini birdan yuklashingiz
     mumkin.
   - Yoki GitHub'ning brauzer versiyasidan "Add file → Create new file"
     orqali har bir faylni nomi bilan yaratib, ichiga matnni joylashtiring.
4. **`.env` faylini hech qachon GitHub'ga yuklamang** — u faqat sizning
   shaxsiy `BOT_TOKEN`ingizni saqlaydi va `.gitignore` orqali repo'dan
   chetlab o'tilgan.

### 3-qadam: Render'da hisob ochish

1. Telefon brauzerida **render.com** saytiga kiring.
2. **"Get Started"** tugmasi orqali ro'yxatdan o'ting — eng qulayi, GitHub
   hisobingiz bilan kirish (**"Sign up with GitHub"**).
3. Render'ga GitHub repository'laringizni ko'rish uchun ruxsat bering.

### 4-qadam: Yangi "Background Worker" yaratish

Bot long polling bilan ishlagani uchun (webhook shart emas), Render'da uni
**Web Service** emas, **Background Worker** sifatida ishga tushiramiz.

1. Render dashboard'da **"New +"** tugmasini bosing.
2. **"Background Worker"** ni tanlang.
3. GitHub repository ro'yxatidan `sarlo-uz-bot` repository'ni tanlang.
4. Render `render.yaml` faylini avtomatik aniqlaydi va sozlamalarni
   (`buildCommand: pip install -r requirements.txt`,
   `startCommand: python bot.py`) o'zi to'ldiradi. Agar avtomatik
   aniqlanmasa, quyidagilarni qo'lda kiriting:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. **Environment Variables** bo'limida quyidagini qo'shing:
   - **Key:** `BOT_TOKEN`
   - **Value:** BotFather'dan olgan tokeningiz
6. **"Create Background Worker"** (yoki "Deploy") tugmasini bosing.

### 5-qadam: Ishga tushganini tekshirish

1. Render dashboard'da worker'ning **"Logs"** bo'limini oching.
2. `SARLO_UZ bot ishga tushmoqda (long polling)...` degan xabarni
   ko'rsangiz — bot ishga tushgan.
3. Telegram'da o'z botingizga o'ting, `/start` yuboring — javob kelishi
   kerak.
4. Xweardan olingan mahsulot postini (matn yoki rasm + caption) yuboring —
   bot tayyor SARLO_UZ formatidagi postni qaytaradi.

### Keyingi yangilanishlar

Kodga o'zgartirish kiritmoqchi bo'lsangiz:

1. GitHub ilovasida faylni tahrirlang va commit qiling.
2. Render avtomatik ravishda yangi commit'ni aniqlab, botni qayta deploy
   qiladi (agar "Auto-Deploy" yoqilgan bo'lsa — bu odatda standart holat).

## Eslatma

- Telegram caption (rasm ostidagi matn) uzunligi 1024 belgi bilan
  cheklangan. Agar tayyor matn undan uzun bo'lsa, bot rasmni qisqa caption
  bilan, to'liq matnni esa alohida xabar sifatida yuboradi.
- Tarjima oddiy lug'at asosida ishlaganligi sababli, lug'atda yo'q noyob
  so'zlar (masalan kamdan-kam uchraydigan mahsulot nomlari) tarjima
  qilinmay, original holatda qoladi. Zarur bo'lsa, `bot.py` ichidagi
  `WORD_MAP` lug'atiga yangi so'z-tarjima juftliklarini qo'shishingiz
  mumkin.
