from fastapi import APIRouter, HTTPException, Query

from features.news import service
from features.news.schema import NewsListResponse

router = APIRouter(prefix="/news", tags=["News"])


@router.get("", response_model=NewsListResponse)
async def get_news(category: str = Query(default="전체")):
    if category not in service.CATEGORY_URLS:
        valid = list(service.CATEGORY_URLS.keys())
        raise HTTPException(status_code=400, detail=f"category는 {valid} 중 하나여야 합니다.")

    articles = await service.fetch_articles(category)
    return {"category": category, "articles": articles}
