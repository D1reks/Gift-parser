import os
import asyncio
import logging
from datetime import datetime
from TelegramGifts import TelegramGifts
from aiogram import Bot
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID не задан в переменных окружения")

GIFTS_TO_WATCH = [
    "Artisan Brick",
    "Khabib's Papakha",
    # добавьте остальные
]

previous_floors: dict[str, float] = {}

bot = Bot(token=BOT_TOKEN)
gifts = TelegramGifts()


async def check_gift(gift_name: str):
    try:
        info = gifts.get_gift(gift_name)
        if not info:
            logger.warning(f"Подарок не найден: {gift_name}")
            return

        current_floor = info.get('prices', {}).get('tgmrkt_price_ton')
        if current_floor is None:
            logger.warning(f"Нет цены для {gift_name}")
            return

        prev = previous_floors.get(gift_name)

        if prev is not None and current_floor < prev:
            text = (
                f"🔔 <b>Цена упала!</b>\n\n"
                f"🎁 {gift_name}\n"
                f"📉 Было: {prev:.2f} TON\n"
                f"📉 Стало: {current_floor:.2f} TON\n"
                f"⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            )
            await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
            logger.info(f"Уведомление: {gift_name} {prev} -> {current_floor}")

        previous_floors[gift_name] = current_floor
        logger.info(f"{gift_name}: floor = {current_floor} TON")

    except Exception as e:
        logger.error(f"Ошибка при проверке {gift_name}: {e}")


async def main_loop():
    logger.info(f"Парсер запущен. Отслеживается {len(GIFTS_TO_WATCH)} подарков.")
    while True:
        for gift in GIFTS_TO_WATCH:
            await check_gift(gift)
            await asyncio.sleep(2)
        logger.info(f"Цикл завершён. Следующая проверка через {CHECK_INTERVAL} сек.")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main_loop())