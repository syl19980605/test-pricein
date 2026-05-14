import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.config import NEWSAPI_KEY
from backend.models.schemas import NewsItem
from backend.services.market_data import market_data_service, ASSET_REGISTRY


def _parse_yf_timestamp(item: dict) -> datetime:
    content = item.get("content", item)
    pub = content.get("pubDate") or content.get("providerPublishTime")
    if isinstance(pub, (int, float)):
        return datetime.fromtimestamp(pub, tz=timezone.utc)
    if isinstance(pub, str):
        try:
            return datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class NewsService:
    async def get_news(self, symbol: str, limit: int = 12) -> list[NewsItem]:
        raw = await market_data_service.get_news(symbol)
        items: list[NewsItem] = []

        for entry in raw[:limit]:
            content = entry.get("content", entry)
            title = content.get("title") or entry.get("title", "")
            if not title:
                continue
            provider = content.get("provider", {})
            source = provider.get("displayName") if isinstance(provider, dict) else "Yahoo Finance"
            url = ""
            click = content.get("clickThroughUrl") or content.get("canonicalUrl")
            if isinstance(click, dict):
                url = click.get("url", "")
            elif isinstance(entry.get("link"), str):
                url = entry["link"]

            items.append(
                NewsItem(
                    title=title,
                    source=source or "Yahoo Finance",
                    url=url,
                    published_at=_parse_yf_timestamp(entry),
                    summary=content.get("summary"),
                )
            )

        if NEWSAPI_KEY and len(items) < limit:
            try:
                extra = await self._newsapi_search(symbol, limit - len(items))
                items.extend(extra)
            except Exception:
                pass

        return items

    async def _newsapi_search(self, symbol: str, limit: int) -> list[NewsItem]:
        meta = ASSET_REGISTRY.get(symbol, {})
        query = meta.get("name", symbol)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "sortBy": "publishedAt",
                    "language": "en",
                    "pageSize": limit,
                    "apiKey": NEWSAPI_KEY,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        items = []
        for art in data.get("articles", []):
            items.append(
                NewsItem(
                    title=art.get("title", ""),
                    source=(art.get("source") or {}).get("name", "NewsAPI"),
                    url=art.get("url", ""),
                    published_at=datetime.fromisoformat(
                        art["publishedAt"].replace("Z", "+00:00")
                    ),
                    summary=art.get("description"),
                )
            )
        return items


news_service = NewsService()
