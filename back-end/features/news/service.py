import asyncio
import html as html_mod
import re
import time
from xml.etree import ElementTree as ET

import httpx

CATEGORY_URLS: dict[str, str] = {
    "전체": "https://www.yna.co.kr/rss/news.xml",
    "정치": "https://www.yna.co.kr/rss/politics.xml",
    "경제": "https://www.yna.co.kr/rss/economy.xml",
}

_CACHE_TTL = 600  # 10분
_cache: dict[str, tuple[float, list[dict]]] = {}

_MEDIA_NS = "http://search.yahoo.com/mrss/"
_MAX_ARTICLES = 10
_SCRAPE_CONCURRENCY = 5

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


async def fetch_articles(category: str) -> list[dict]:
    now = time.monotonic()
    if category in _cache:
        ts, data = _cache[category]
        if now - ts < _CACHE_TTL:
            return data

    rss_url = CATEGORY_URLS[category]
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:
        items = await _parse_rss(client, rss_url, category)
        items = items[:_MAX_ARTICLES]
        sem = asyncio.Semaphore(_SCRAPE_CONCURRENCY)

        async def enrich(item: dict) -> dict:
            async with sem:
                item["paragraphs"] = await _scrape_body(client, item["link"])
                return item

        results = await asyncio.gather(*[enrich(i) for i in items], return_exceptions=True)

    articles = [r for r in results if isinstance(r, dict)]
    _cache[category] = (now, articles)
    return articles


async def _parse_rss(client: httpx.AsyncClient, url: str, category: str) -> list[dict]:
    resp = await client.get(url)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)

    items: list[dict] = []
    for el in root.findall(".//item"):
        title = el.findtext("title") or ""
        link = el.findtext("link") or ""
        pub_date = el.findtext("pubDate") or ""
        description = el.findtext("description") or ""

        media = el.find(f"{{{_MEDIA_NS}}}content")
        image_url = media.get("url") if media is not None else None

        if not link:
            continue

        items.append(
            {
                "title": title.strip(),
                "link": link.strip(),
                "category": category,
                "pub_date": pub_date.strip(),
                "image_url": image_url,
                "description": html_mod.unescape(description.strip()),
                "paragraphs": [],
            }
        )

    return items


async def _scrape_body(client: httpx.AsyncClient, url: str) -> list[str]:
    try:
        resp = await client.get(url, timeout=10.0)
        text = resp.text

        idx = text.find("story-news")
        if idx == -1:
            return []

        section = text[idx : idx + 15000]
        raw_paras = re.findall(r"<p[^>]*>(.*?)</p>", section, re.DOTALL)

        result: list[str] = []
        for raw in raw_paras:
            clean = html_mod.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
            if (
                len(clean) < 20
                or clean.startswith("[")
                or "저작권자" in clean
                or "무단 전재" in clean
                or "제보는" in clean
                or "재판매" in clean
            ):
                continue
            result.append(clean)
            if len(result) >= 5:
                break

        return result
    except Exception:
        return []
