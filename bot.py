"""
SARLO_UZ Telegram Bot
---------------------
Xweardan olingan mahsulot e'lonlarini avtomatik ravishda SARLO_UZ formatiga
qayta formatlaydi: narxdan 1000 so'm ayiradi, LOOK nomini almashtiradi,
buyurtma username'ini o'zgartiradi, "Отзыв" qatorini olib tashlaydi va
o'zbekcha tarjimasini qo'shadi.

Texnologiya: Python 3.11+, aiogram 3.x, long polling (webhook talab qilinmaydi).
"""

import asyncio
import logging
import os
import re
from typing import Callable, List, Optional, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Sozlamalar
# --------------------------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. `.env` faylida yoki muhit o'zgaruvchisida "
        "BOT_TOKEN qiymatini belgilang (.env.example fayliga qarang)."
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("sarlo_bot")

SHOP_NAME = "SARLO_UZ"
ORDER_USERNAME = "@sarlo_admin"
PRICE_DEDUCTION = 1000
TELEGRAM_CAPTION_LIMIT = 1024

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --------------------------------------------------------------------------
# Regexlar
# --------------------------------------------------------------------------

LOOK_RE = re.compile(r"^(?P<bullet>[•\-\*]?\s*)LOOK\s*:\s*.*$", re.IGNORECASE)
DIVIDER_RE = re.compile(r"^[—\-_=]{5,}\s*$")
REVIEW_RE = re.compile(r".*\b(отзыв\w*|review\w*|isbot)\b.*", re.IGNORECASE)
ORDER_RE = re.compile(
    r"^(?P<bullet>[•\-\*]?\s*)(?:Для\s+заказа|Заказ|Order|Buyurtma\s+uchun)\s*:\s*(?P<user>@?\S+)",
    re.IGNORECASE,
)

# Narxni aniqlaydigan asosiy regex: 400.000 / 400 000 / 400,000 / 400000 / 400k / $50
PRICE_LINE_RE = re.compile(
    r"(?:(?P<currency>\$|USD)\s*)?"
    r"(?P<num>\d{1,3}(?:[.,\s]\d{3})+|\d{4,}|\d{1,3}(?=\s*[kK]\b))"
    r"(?P<ksuffix>\s*[kK]\b)?",
)

EXCLUDE_PRICE_LINE_KEYWORDS = (
    "карго",
    "cargo",
    "предоплат",
    "скидк",
    "наличи",
    "размер",
    "gr",
    "гр",
)

# --------------------------------------------------------------------------
# Tarjima lug'atlari va qoidalari
# --------------------------------------------------------------------------

# Butun qatorni almashtiradigan aniq iboralar (regex -> template funksiyasi)
PhraseRule = Tuple[re.Pattern, Callable[[re.Match], str]]

PHRASE_RULES: List[PhraseRule] = [
    (
        re.compile(r"Карго\s*(\d+)\s*г?р\.?\s*=\s*([\d.,\s]+)", re.IGNORECASE),
        lambda m: f"Kargo {m.group(1)}gr = {m.group(2).strip()}",
    ),
    (
        re.compile(r"Предоплата\s*(\d+)\s*%", re.IGNORECASE),
        lambda m: f"Oldindan to'lov {m.group(1)}%",
    ),
    (
        re.compile(r"Доставка\s+по\s+Узбекистану", re.IGNORECASE),
        lambda m: "O'zbekiston bo'ylab yetkazib berish",
    ),
    (
        re.compile(r"Размеры\s+в\s+наличии", re.IGNORECASE),
        lambda m: "Razmerlar mavjud",
    ),
    (
        re.compile(r"Для\s+заказа\s*:", re.IGNORECASE),
        lambda m: "Buyurtma uchun:",
    ),
]

# Yakka so'zlar uchun zaxira lug'at (rang, material va boshqa umumiy so'zlar)
WORD_MAP = {
    # ranglar
    "черный": "qora", "чёрный": "qora", "белый": "oq", "серый": "kulrang",
    "красный": "qizil", "синий": "ko'k", "голубой": "moviy",
    "зеленый": "yashil", "зелёный": "yashil", "желтый": "sariq", "жёлтый": "sariq",
    "розовый": "pushti", "фиолетовый": "binafsha", "оранжевый": "to'q sariq",
    "коричневый": "jigarrang", "бежевый": "bej", "бордовый": "bordo",
    "хаки": "xaki", "серебристый": "kumush rang", "золотой": "oltin rang",
    # materiallar
    "хлопок": "paxta", "кожа": "teri", "замша": "zamsha", "джинс": "jins",
    "шелк": "ipak", "шёлк": "ipak", "шерсть": "jun", "полиэстер": "poliester",
    "трикотаж": "trikotaj", "вельвет": "velvet", "флис": "flis",
    # umumiy so'zlar
    "цвет": "rang", "цвета": "ranglar", "размер": "o'lcham", "размеры": "o'lchamlar",
    "материал": "material", "модель": "model", "качество": "sifat",
    "новинка": "yangilik", "скидка": "chegirma", "наличии": "mavjud",
    "наличие": "mavjud", "заказ": "buyurtma", "заказа": "buyurtma",
    "доставка": "yetkazib berish", "оплата": "to'lov", "предоплата": "oldindan to'lov",
    "рост": "bo'y", "вес": "vazn", "унисекс": "unisex", "мужской": "erkaklar",
    "женский": "ayollar", "детский": "bolalar", "хит": "hit", "продаж": "sotuv",
}

CYRILLIC_WORD_RE = re.compile(r"[А-Яа-яЁё]+")


def translate_words(line: str) -> str:
    """Lug'atda mavjud bo'lgan alohida so'zlarni o'zbekchaga almashtiradi."""

    def repl(m: re.Match) -> str:
        word = m.group(0)
        translated = WORD_MAP.get(word.lower())
        if not translated:
            return word
        if word[0].isupper():
            translated = translated[0].upper() + translated[1:]
        return translated

    return CYRILLIC_WORD_RE.sub(repl, line)


def translate_line(line: str) -> str:
    """Qatorni avval aniq iboralar bo'yicha, so'ng so'z-so'z tarjima qiladi."""
    result = line
    matched_any = False
    for pattern, repl in PHRASE_RULES:
        if pattern.search(result):
            result = pattern.sub(lambda m, r=repl: r(m), result)
            matched_any = True
    if not matched_any:
        result = translate_words(result)
    return result


# --------------------------------------------------------------------------
# Narx bilan ishlash
# --------------------------------------------------------------------------

def parse_number(num_str: str, k_suffix: Optional[str]) -> int:
    cleaned = re.sub(r"[.,\s]", "", num_str)
    value = int(cleaned)
    if k_suffix:
        value *= 1000
    return value


def format_price(value: int) -> str:
    """O'zbekiston uslubida narxni formatlaydi: 599000 -> 599.000"""
    s = str(value)
    parts = []
    while len(s) > 3:
        parts.insert(0, s[-3:])
        s = s[:-3]
    parts.insert(0, s)
    return ".".join(parts)


def find_main_price_line(lines: List[str]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Asosiy mahsulot narxi joylashgan qatorni topadi (cargo narxini hisobga olmay)."""
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if any(keyword in low for keyword in EXCLUDE_PRICE_LINE_KEYWORDS):
            continue
        if LOOK_RE.match(stripped) or DIVIDER_RE.match(stripped):
            continue
        if ORDER_RE.match(stripped) or REVIEW_RE.match(stripped):
            continue
        m = PRICE_LINE_RE.search(stripped)
        if m and m.group("num"):
            currency = m.group("currency")
            value = parse_number(m.group("num"), m.group("ksuffix"))
            return idx, value, currency
    return None, None, None


def replace_price_in_line(line: str, value: int, currency: Optional[str]) -> str:
    is_usd = bool(currency)
    new_value = value if is_usd else value - PRICE_DEDUCTION
    formatted = format_price(new_value)
    replacement = f"{currency}{formatted}" if is_usd else formatted

    def do_replace(m: re.Match) -> str:
        return replacement

    return PRICE_LINE_RE.sub(do_replace, line, count=1)


# --------------------------------------------------------------------------
# Asosiy qayta ishlash funksiyasi
# --------------------------------------------------------------------------

def process_post(raw_text: str) -> str:
    lines = raw_text.replace("\r\n", "\n").split("\n")

    main_price_idx, main_price_value, main_price_currency = find_main_price_line(lines)

    output_lines: List[str] = []
    price_out_idx: Optional[int] = None
    look_out_idx: Optional[int] = None
    divider_out_idx: Optional[int] = None

    for idx, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            output_lines.append(line)
            continue

        if REVIEW_RE.match(stripped):
            # Отзыв qatorini butunlay olib tashlaymiz
            continue

        if DIVIDER_RE.match(stripped):
            divider_out_idx = len(output_lines)
            output_lines.append(line)
            continue

        if LOOK_RE.match(stripped):
            new_line = re.sub(r"LOOK\s*:\s*.*", f"LOOK: {SHOP_NAME}", line, flags=re.IGNORECASE)
            look_out_idx = len(output_lines)
            output_lines.append(new_line)
            continue

        if ORDER_RE.match(stripped):
            new_line = re.sub(r"@\S+", ORDER_USERNAME, line)
            output_lines.append(new_line)
            continue

        if idx == main_price_idx:
            new_line = replace_price_in_line(line, main_price_value, main_price_currency)
            price_out_idx = len(output_lines)
            output_lines.append(new_line)
            continue

        output_lines.append(line)

    # Bosh va oxiridagi bo'sh qatorlarni olib tashlash
    while output_lines and not output_lines[0].strip():
        output_lines.pop(0)
    while output_lines and not output_lines[-1].strip():
        output_lines.pop()

    russian_part = "\n".join(output_lines)

    # --- O'zbekcha versiyani tuzish ---
    skip_indices = {i for i in (price_out_idx, look_out_idx, divider_out_idx) if i is not None}
    uzbek_lines: List[str] = []
    for i, line in enumerate(output_lines):
        if i in skip_indices:
            continue
        if not line.strip():
            uzbek_lines.append(line)
            continue
        uzbek_lines.append(translate_line(line))

    while uzbek_lines and not uzbek_lines[0].strip():
        uzbek_lines.pop(0)
    while uzbek_lines and not uzbek_lines[-1].strip():
        uzbek_lines.pop()

    uzbek_part = "\n".join(uzbek_lines)

    if uzbek_part.strip():
        final_text = f"{russian_part}\n\n🇺🇿 O‘ZBEKCHA\n\n{uzbek_part}"
    else:
        final_text = russian_part

    return final_text


# --------------------------------------------------------------------------
# Telegram handlerlar
# --------------------------------------------------------------------------

START_TEXT = (
    "Salom! 👋\n\n"
    "Xweardagi mahsulot e'lonini shu yerga yuboring.\n\n"
    "Men avtomatik:\n"
    "💰 Narxdan 1 000 so'm ayiraman\n"
    "🏷️ SARLO_UZ formatiga o'zgartiraman\n"
    "🇺🇿 O'zbekcha versiyasini qo'shaman\n\n"
    "va tayyor postni qaytaraman.\n\n"
    "Matn yuborsangiz — tayyor matn qaytadi.\n"
    "Rasm + caption yuborsangiz — rasm + yangi caption qaytadi."
)


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(START_TEXT)


@dp.message(F.photo)
async def handle_photo(message: Message) -> None:
    caption = message.caption or ""
    if not caption.strip():
        await message.answer(
            "Rasm bilan birga mahsulot ma'lumotlari yozilgan caption (izoh) yuboring, iltimos."
        )
        return

    try:
        new_caption = process_post(caption)
    except Exception:
        logger.exception("Caption qayta ishlashda xatolik yuz berdi")
        await message.answer("Kechirasiz, caption'ni qayta ishlashda xatolik yuz berdi.")
        return

    photo_file_id = message.photo[-1].file_id

    if len(new_caption) <= TELEGRAM_CAPTION_LIMIT:
        await message.answer_photo(photo=photo_file_id, caption=new_caption)
    else:
        # Telegram caption uzunligi cheklangan (1024 belgi) — shuning uchun
        # rasmni qisqa caption bilan, to'liq matnni esa alohida xabar sifatida yuboramiz.
        await message.answer_photo(
            photo=photo_file_id,
            caption="Tayyor matn quyidagi xabarda 👇 (caption uzun bo'lgani uchun)",
        )
        await message.answer(new_caption)


@dp.message(F.text)
async def handle_text(message: Message) -> None:
    text = message.text or ""
    try:
        new_text = process_post(text)
    except Exception:
        logger.exception("Matnni qayta ishlashda xatolik yuz berdi")
        await message.answer("Kechirasiz, matnni qayta ishlashda xatolik yuz berdi.")
        return

    await message.answer(new_text)


# --------------------------------------------------------------------------
# Ishga tushirish (long polling, webhook talab qilinmaydi)
# --------------------------------------------------------------------------

async def main() -> None:
    logger.info("SARLO_UZ bot ishga tushmoqda (long polling)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
