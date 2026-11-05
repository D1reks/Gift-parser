import asyncio
import json
import logging
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

GETGEMS_GQL = "https://api.getgems.io/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; probe/1.0)",
    "Origin": "https://getgems.io",
    "Referer": "https://getgems.io/",
}

# Известный адрес коллекции Artisan Brick на GetGems (проверим, что рабочий)
# Если не найдётся — заменим на актуальный через поиск
ARTISAN_BRICK = "EQAo92DYMokxghKcqynUVHh9y0f-4bG0irJZbNsAqSj5v0eO"


async def gql(session: aiohttp.ClientSession, query: str, variables: dict, label: str):
    logger.info(f"--- {label} ---")
    try:
        async with session.post(
            GETGEMS_GQL,
            json={"query": query, "variables": variables},
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            text = await resp.text()
            logger.info(f"HTTP {resp.status}")
            if resp.status != 200:
                logger.warning(f"Тело ответа (первые 500): {text[:500]}")
                return None
            try:
                data = json.loads(text)
            except Exception as e:
                logger.error(f"Не JSON: {e}. Тело: {text[:500]}")
                return None
            if "errors" in data:
                logger.warning(f"GraphQL errors: {json.dumps(data['errors'], ensure_ascii=False)[:800]}")
            return data
    except Exception as e:
        logger.exception(f"Ошибка запроса: {e}")
        return None


async def probe_collection_nfts(session: aiohttp.ClientSession):
    """Тянем активные лоты одной коллекции, смотрим структуру."""
    query = """
    query Nfts($collectionAddress: String!, $first: Int!) {
      alphaNftCollection(address: $collectionAddress) {
        address
        name
        nfts(first: $first, filter: { status: { eq: ON_SALE } }) {
          edges {
            node {
              address
              name
              sale {
                price { amount }
              }
              attributes {
                traitType
                value
              }
            }
          }
        }
      }
    }
    """
    data = await gql(
        session, query,
        {"collectionAddress": ARTISAN_BRICK, "first": 5},
        "Структура лотов коллекции (Artisan Brick)",
    )
    if not data or "data" not in data:
        return
    col = (data.get("data") or {}).get("alphaNftCollection")
    if not col:
        logger.warning("alphaNftCollection = null — адрес коллекции неверный или схема изменилась")
        return
    nfts = col.get("nfts", {}).get("edges", [])
    logger.info(f"Лотов получено: {len(nfts)}")
    for i, edge in enumerate(nfts, 1):
        node = edge.get("node", {})
        price = (node.get("sale") or {}).get("price") or {}
        amount = price.get("amount")
        attrs = node.get("attributes") or []
        bg = [a for a in attrs if "background" in (a.get("traitType") or "").lower()]
        logger.info(
            f"  [{i}] addr={node.get('address')[:16]}... "
            f"price_nano={amount} "
            f"bg={bg} "
            f"all_attrs={attrs[:4]}"
        )


async def probe_global_search(session: aiohttp.ClientSession):
    """Пробуем глобальный поиск лотов с фильтром по трейтам.
    Если такого эндпоинта нет — увидим GraphQL errors, это тоже результат.
    """
    # Гипотеза 1: alphaNfts с фильтром по атрибутам
    query1 = """
    query SearchByTrait($first: Int!) {
      alphaNfts(
        first: $first,
        filter: { status: { eq: ON_SALE } }
      ) {
        edges {
          node {
            address
            name
            sale { price { amount } }
            attributes { traitType value }
          }
        }
      }
    }
    """
    await gql(session, query1, {"first": 3}, "Гипотеза 1: alphaNfts (глобальный список лотов)")

    # Гипотеза 2: поиск коллекций + их лоты — на случай, если глобального нет
    query2 = """
    query Collections($first: Int!) {
      alphaNftCollections(first: $first) {
        edges {
          node {
            address
            name
          }
        }
      }
    }
    """
    await gql(session, query2, {"first": 5}, "Гипотеза 2: список коллекций (для обхода по одной)")


async def main():
    async with aiohttp.ClientSession() as session:
        await probe_collection_nfts(session)
        await probe_global_search(session)
        logger.info("=== Диагностика завершена ===")


if __name__ == "__main__":
    asyncio.run(main())