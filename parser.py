import os
import asyncio
import logging
from datetime import datetime
from TelegramGifts import TelegramGifts
from aiogram import Bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в переменных окружения")
if not CHAT_ID:
    raise RuntimeError("CHAT_ID не задан в переменных окружения")

try:
    CHAT_ID = int(CHAT_ID)
except ValueError:
    raise RuntimeError(f"CHAT_ID должен быть числом, получено: {CHAT_ID!r}")

logger.info(f"Конфигурация: CHAT_ID={CHAT_ID}, CHECK_INTERVAL={CHECK_INTERVAL}s")

GIFTS_TO_WATCH = [
    "Artisan Brick",
    "Khabib's Papakha",
]

# Хранилище предыдущих floor-цен (в памяти — сбрасывается при рестарте)
previous_floors: dict[str, float] = {}

bot = Bot(token=BOT_TOKEN)
gifts = TelegramGifts()


async def debug_gifts():
    """Диагностика: показывает доступные подарки и ищет похожие на Khabib."""
    logger.info("=== ДИАГНОСТИКА ПОДАРКОВ ===")
    try:
        all_gifts = None
        for method_name in ("get_all_gifts", "list_gifts", "get_gifts"):
            if hasattr(gifts, method_name):
                method = getattr(gifts, method_name)
                try:
                    all_gifts = method()
                    logger.info(f"Использован метод: {method_name}")
                    break
                except Exception as e:
                    logger.warning(f"Метод {method_name} упал: {e}")

        if all_gifts is None:
            logger.warning("Не найден метод для получения списка подарков. "
                           "Проверьте версию библиотеки TelegramGifts.")
            return

        if isinstance(all_gifts, dict):
            names = list(all_gifts.keys())
        elif isinstance(all_gifts, list):
            names = [
                g.get("name") if isinstance(g, dict) else str(g)
                for g in all_gifts
            ]
        else:
            logger.warning(f"Неизвестный формат списка: {type(all_gifts)}")
            return

        names = [n for n in names if n]
        logger.info(f"Всего подарков в кэше: {len(names)}")

        for n in names:
            low = n.lower()
            if "khabib" in low or "papakha" in low:
                logger.info(f"  найдено похожее: {n!r}")

        # Также покажем первые 10 для ориентира
        logger.info("Первые 10 подарков в кэше:")
        for n in names[:10]:
            logger.info(f"  {n!r}")

    except Exception as e:
        logger.exception(f"Ошибка диагностики: {e}")


async def send_telegram(text: str, label: str = "") -> bool:
    """Отправляет сообщение с явным логированием результата."""
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
        logger.info(f"✅ Отправлено в Telegram ({label or 'msg'})")
        return True
    except Exception as e:
        logger.error(f"❌ Не удалось отправить в {CHAT_ID} ({label or 'msg'}): {e}")
        return False


async def check_gift(gift_name: str):
    try:
        info = gifts.get_gift(gift_name)
        if not info:
            logger.warning(f"Подарок не найден: {gift_name!r}")
            return

        current_floor = info.get("prices", {}).get("tgmrkt_price_ton")
        if current_floor is None:
            logger.warning(f"Нет цены для {gift_name!r}: {info.get('prices')}")
            return

        prev = previous_floors.get(gift_name)

        if prev is None:
            logger.info(f"{gift_name}: первичное значение floor = {current_floor} TON")
        elif current_floor < prev:
            text = (
                f"🔔 <b>Цена упала!</b>\n\n"
                f"🎁 {gift_name}\n"
                f"📉 Было: {prev:.2f} TON\n"
                f"📉 Стало: {current_floor:.2f} TON\n"
                f"⏰ {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            )
            await send_telegram(text, label=f"падение {gift_name}")
            logger.info(f"{gift_name}: {prev} -> {current_floor} TON (уведомление)")
        else:
            logger.info(f"{gift_name}: floor = {current_floor} TON (без изменений или рост)")

        previous_floors[gift_name] = current_floor

    except Exception as e:
        logger.exception(f"Ошибка при проверке {gift_name!r}: {e}")


async def main_loop():
    logger.info(f"Парсер запущен. Отслеживается {len(GIFTS_TO_WATCH)} подарков.")

    await debug_gifts()

    # Тестовое сообщение, чтобы убедиться, что связка BOT_TOKEN + CHAT_ID + /start работает
    await send_telegram(
        "✅ Парсер запущен. Уведомления подключены.",
        label="тест при старте",
    )

    while True:
        for gift in GIFTS_TO_WATCH:
            await check_gift(gift)
            await asyncio.sleep(2)
        logger.info(f"Цикл завершён. Следующая проверка через {CHECK_INTERVAL} сек.")
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main_loop())