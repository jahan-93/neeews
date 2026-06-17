import asyncio
import time
from collections import Counter

from kiwipiepy import Kiwi

from features.news.service import SOURCE_FEEDS, _get_or_fetch_source

_kiwi: Kiwi | None = None
_CACHE_TTL = 600
_cache: dict[str, tuple[float, list[dict]]] = {}

# 분석에서 제외할 불용어
_STOPWORDS: set[str] = {
    "것", "수", "등", "및", "이", "그", "저", "때", "중", "곳", "바",
    "뒤", "앞", "위", "말", "날", "점", "안", "밖", "년", "월", "일",
    "하다", "되다", "있다", "없다", "않다", "이다", "아니다",
    "위해", "통해", "대해", "관련", "가운데", "이후", "이전",
    "때문", "경우", "대한", "지난", "다음", "최근", "현재",
    "기자", "기사", "뉴스", "보도", "특파원", "논설", "칼럼",
    "서비스", "시스템", "플랫폼", "솔루션", "프로젝트",
}


def _get_kiwi() -> Kiwi:
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


async def get_keywords(source: str, top_n: int = 10) -> list[dict]:
    now = time.monotonic()
    if source in _cache:
        ts, data = _cache[source]
        if now - ts < _CACHE_TTL:
            return data

    if source == "전체":
        results = await asyncio.gather(
            *[_get_or_fetch_source(src) for src in SOURCE_FEEDS.keys()],
            return_exceptions=True,
        )
        articles: list[dict] = []
        for r in results:
            if isinstance(r, list):
                articles.extend(r)
    else:
        articles = await _get_or_fetch_source(source)

    texts: list[str] = []
    for a in articles:
        if a.get("title"):
            texts.append(a["title"])
        if a.get("description"):
            texts.append(a["description"])

    loop = asyncio.get_running_loop()
    keywords = await loop.run_in_executor(None, _analyze, "\n".join(texts), top_n)

    _cache[source] = (now, keywords)
    return keywords


def _analyze(text: str, top_n: int) -> list[dict]:
    kiwi = _get_kiwi()
    tokens = kiwi.tokenize(text)

    counter: Counter = Counter()
    for token in tokens:
        # NNG: 일반명사, NNP: 고유명사, SL: 외래어(영문 기술용어 등)
        if token.tag not in ("NNG", "NNP", "SL"):
            continue
        word = token.form
        if len(word) < 2:
            continue
        if word in _STOPWORDS:
            continue
        counter[word] += 1

    return [{"keyword": w, "count": c} for w, c in counter.most_common(top_n)]
