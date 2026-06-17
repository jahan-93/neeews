from fastapi import APIRouter, HTTPException, Query

from features.news import service
from features.news.schema import NewsListResponse

router = APIRouter(prefix="/news", tags=["News"])


@router.get("", response_model=NewsListResponse)
async def get_news(source: str = Query(default="전체")):
    if source not in service.SOURCES:
        raise HTTPException(status_code=400, detail=f"source는 {service.SOURCES} 중 하나여야 합니다.")

    articles = await service.fetch_articles(source)
    return {"source": source, "articles": articles}
