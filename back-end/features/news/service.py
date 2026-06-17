import asyncio
import html as html_mod
import re
import time
from xml.etree import ElementTree as ET

import httpx

SOURCE_FEEDS: dict[str, str] = {
    "연합뉴스": "https://www.yna.co.kr/rss/news.xml",
    "전자신문": "https://rss.etnews.com/Section901.xml",
    "ZDNet코리아": "https://zdnet.co.kr/feed/",
    "동아일보": "https://rss.donga.com/total.xml",
    "경향신문": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
}

SOURCES: list[str] = ["전체"] + list(SOURCE_FEEDS.keys())

_CACHE_TTL = 600
_cache: dict[str, tuple[float, list[dict]]] = {}

_MEDIA_NS = "http://search.yahoo.com/mrss/"
_CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
_MAX_ARTICLES = 30
_SCRAPE_CONCURRENCY = 5

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 각 언론사 기사 본문 탐색 키워드 (HTML에서 순서대로 시도)
_BODY_SELECTORS: dict[str, list[str]] = {
    "연합뉴스": ["story-news"],
    "전자신문": ["article_body", "news_view", "articleView"],
    "ZDNet코리아": ["news_view_cnt", "article_content", "view_content"],
    "동아일보": ["article_txt", "news_view_box"],
    "경향신문": ["art_body", "article_body"],
}

_SKIP_PATTERNS: list[str] = [
    "저작권자", "무단 전재", "제보는", "재판매", "무단전재",
    "Copyright", "All rights reserved", "©",
]


async def fetch_articles(source: str) -> list[dict]:
    if source == "전체":
        results = await asyncio.gather(
            *[_get_or_fetch_source(src) for src in SOURCE_FEEDS.keys()],
            return_exceptions=True,
        )
        articles: list[dict] = []
        for r in results:
            if isinstance(r, list):
                articles.extend(r[:30])
        return articles
    return await _get_or_fetch_source(source)


async def _get_or_fetch_source(source: str) -> list[dict]:
    now = time.monotonic()
    if source in _cache:
        ts, data = _cache[source]
        if now - ts < _CACHE_TTL:
            return data

    articles = await _fetch_from_rss(source, SOURCE_FEEDS[source])
    _cache[source] = (now, articles)
    return articles


async def _fetch_from_rss(source: str, url: str) -> list[dict]:
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
        headers=_HEADERS,
    ) as client:
        items = await _parse_rss(client, url, source)
        items = items[:_MAX_ARTICLES]

        sem = asyncio.Semaphore(_SCRAPE_CONCURRENCY)

        async def enrich(item: dict) -> dict:
            async with sem:
                if not item["paragraphs"]:
                    item["paragraphs"] = await _scrape_body(client, item["link"], source)
                return item

        results = await asyncio.gather(*[enrich(i) for i in items], return_exceptions=True)

    return [r for r in results if isinstance(r, dict)]


async def _parse_rss(client: httpx.AsyncClient, url: str, source: str) -> list[dict]:
    resp = await client.get(url)
    resp.raise_for_status()

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        return []
    items: list[dict] = []

    for el in root.findall(".//item"):
        title = el.findtext("title") or ""
        link = el.findtext("link") or ""
        pub_date = el.findtext("pubDate") or ""
        description = el.findtext("description") or ""
        category = el.findtext("category") or ""
        category = html_mod.unescape(re.sub(r"<[^>]+>", "", category)).strip()

        image_url: str | None = None
        media_content = el.find(f"{{{_MEDIA_NS}}}content")
        if media_content is not None:
            image_url = media_content.get("url")
        if image_url is None:
            media_thumb = el.find(f"{{{_MEDIA_NS}}}thumbnail")
            if media_thumb is not None:
                image_url = media_thumb.get("url")

        # content:encoded 또는 description HTML에서 본문/이미지 추출
        content_encoded = el.findtext(f"{{{_CONTENT_NS}}}encoded") or ""
        paragraphs: list[str] = []
        rich_html = content_encoded or (description if source in ("동아일보", "경향신문") else "")
        if rich_html:
            paragraphs = _extract_paragraphs_from_html(rich_html)
            if not image_url:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', rich_html)
                if img_match:
                    image_url = img_match.group(1)

        # 어느 언론사든 description에 이미지가 있으면 fallback으로 추출
        if not image_url and description:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description)
            if img_match:
                image_url = img_match.group(1)

        if not link:
            continue

        plain_desc = html_mod.unescape(re.sub(r"<[^>]+>", "", description)).strip()

        items.append({
            "title": title.strip(),
            "link": link.strip(),
            "source": source,
            "category": category,
            "pub_date": pub_date.strip(),
            "image_url": image_url,
            "description": plain_desc,
            "paragraphs": paragraphs,
        })

    return items


def _extract_paragraphs_from_html(html: str, max_paras: int = 5) -> list[str]:
    raw_paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
    result: list[str] = []
    for raw in raw_paras:
        clean = html_mod.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
        if len(clean) < 20:
            continue
        if any(pat in clean for pat in _SKIP_PATTERNS):
            continue
        result.append(clean)
        if len(result) >= max_paras:
            break
    return result


async def _scrape_body(client: httpx.AsyncClient, url: str, source: str) -> list[str]:
    selectors = _BODY_SELECTORS.get(source, [])
    if not selectors:
        return []

    try:
        resp = await client.get(url, timeout=10.0)
        text = resp.text

        for selector in selectors:
            idx = text.find(selector)
            if idx == -1:
                continue

            section = text[idx: idx + 15000]
            raw_paras = re.findall(r"<p[^>]*>(.*?)</p>", section, re.DOTALL)

            result: list[str] = []
            for raw in raw_paras:
                clean = html_mod.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
                if len(clean) < 20:
                    continue
                if any(pat in clean for pat in _SKIP_PATTERNS):
                    continue
                result.append(clean)
                if len(result) >= 5:
                    break

            if result:
                return result

        return []
    except Exception:
        return []
