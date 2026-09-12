"""
SARLO_UZ Telegram Bot
---------------------
Xweardan olingan mahsulot e'lonlarini avtomatik ravishda SARLO_UZ formatiga
qayta formatlaydi: narxdan 1000 so'm ayiradi, LOOK nomini almashtiradi,
buyurtma username'ini o'zgartiradi va "Отзыв" qatorini olib tashlaydi.

Texnologiya: Python 3.11+, aiogram 3.x, long polling (webhook talab qilinmaydi).
"""

import asyncio
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import InputMediaPhoto, Message
from aiohttp import web
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

LOOK_RE = re.compile(r"LOOK\s*:\s*\S+", re.IGNORECASE)
DIVIDER_RE = re.compile(r"^[—\-_=]{5,}\s*$")
REVIEW_RE = re.compile(r".*\b(отзыв\w*|review\w*|isbot)\b.*", re.IGNORECASE)
ORDER_RE = re.compile(
    r"(?:Для\s+заказа|Заказ|Order|Buyurtma\s+uchun)\s*:\s*@?\S+",
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

# Media Group (Albom) buferi: media_group_id -> [Message]
MEDIA_GROUPS: Dict[str, List[Message]] = {}

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
        if DIVIDER_RE.match(stripped) or REVIEW_RE.match(stripped):
            continue
        if ORDER_RE.search(stripped):
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

    for idx, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            output_lines.append(line)
            continue

        if REVIEW_RE.match(stripped):
            # Отзыв qatorini butunlay olib tashlaymiz
            continue

        processed_line = line

        if LOOK_RE.search(processed_line):
            processed_line = LOOK_RE.sub(f"LOOK: {SHOP_NAME}", processed_line)

        if ORDER_RE.search(processed_line):
            processed_line = re.sub(r"@\S+", ORDER_USERNAME, processed_line)

        if idx == main_price_idx:
            processed_line = replace_price_in_line(processed_line, main_price_value, main_price_currency)

        output_lines.append(processed_line)

    # Bosh va oxiridagi bo'sh qatorlarni olib tashlash
    while output_lines and not output_lines[0].strip():
        output_lines.pop(0)
    while output_lines and not output_lines[-1].strip():
        output_lines.pop()

    return "\n".join(output_lines)


# --------------------------------------------------------------------------
# Telegram handlerlar
# --------------------------------------------------------------------------

START_TEXT = (
    "Salom! 👋\n\n"
    "Xweardagi mahsulot e'lonini shu yerga yuboring.\n\n"
    "Men avtomatik:\n"
    "💰 Narxdan 1 000 so'm ayiraman\n"
    "🏷️ SARLO_UZ formatiga o'zgartiraman\n"
    "👤 Buyurtma username'ini @sarlo_admin ga o'zgartiraman\n\n"
    "va tayyor postni qaytaraman.\n\n"
    "Matn yuborsangiz — tayyor matn qaytadi.\n"
    "Rasm / albom + caption yuborsangiz — rasm / albom + yangi caption qaytadi."
)


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(START_TEXT)


async def process_media_group(messages: List[Message]) -> None:
    messages.sort(key=lambda m: m.message_id)

    caption = ""
    for msg in messages:
        if msg.caption and msg.caption.strip():
            caption = msg.caption
            break

    if not caption.strip():
        await messages[0].answer(
            "Rasm bilan birga mahsulot ma'lumotlari yozilgan caption (izoh) yuboring, iltimos."
        )
        return

    try:
        new_caption = process_post(caption)
    except Exception:
        logger.exception("Caption qayta ishlashda xatolik yuz berdi")
        await messages[0].answer("Kechirasiz, caption'ni qayta ishlashda xatolik yuz berdi.")
        return

    media_group: List[InputMediaPhoto] = []
    for idx, msg in enumerate(messages):
        photo_file_id = msg.photo[-1].file_id
        if idx == 0:
            if len(new_caption) <= TELEGRAM_CAPTION_LIMIT:
                media_group.append(
                    InputMediaPhoto(media=photo_file_id, caption=new_caption)
                )
            else:
                media_group.append(
                    InputMediaPhoto(
                        media=photo_file_id,
                        caption="Tayyor matn quyidagi xabarda 👇 (caption uzun bo'lgani uchun)",
                    )
                )
        else:
            media_group.append(InputMediaPhoto(media=photo_file_id))

    await messages[0].answer_media_group(media=media_group)

    if len(new_caption) > TELEGRAM_CAPTION_LIMIT:
        await messages[0].answer(new_caption)


async def process_single_photo(message: Message) -> None:
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
        await message.answer_photo(
            photo=photo_file_id,
            caption="Tayyor matn quyidagi xabarda 👇 (caption uzun bo'lgani uchun)",
        )
        await message.answer(new_caption)


@dp.message(F.photo)
async def handle_photo(message: Message) -> None:
    if message.media_group_id:
        mg_id = message.media_group_id
        if mg_id not in MEDIA_GROUPS:
            MEDIA_GROUPS[mg_id] = [message]
            await asyncio.sleep(0.6)
            messages = MEDIA_GROUPS.pop(mg_id, [])
            if messages:
                await process_media_group(messages)
        else:
            MEDIA_GROUPS[mg_id].append(message)
    else:
        await process_single_photo(message)


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

async def start_healthcheck_server() -> None:
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="SARLO_UZ Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Healthcheck web server started on port {port}")


async def main() -> None:
    logger.info("SARLO_UZ bot ishga tushmoqda...")
    await start_healthcheck_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
