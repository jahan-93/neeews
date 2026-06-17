from fastapi import APIRouter, HTTPException, Query

from features.keywords import service
from features.keywords.schema import KeywordsResponse
from features.news.service import SOURCES

router = APIRouter(prefix="/keywords", tags=["Keywords"])


@router.get("", response_model=KeywordsResponse)
async def get_keywords(source: str = Query(default="전체")):
    if source not in SOURCES:
        raise HTTPException(status_code=400, detail=f"source는 {SOURCES} 중 하나여야 합니다.")

    keywords = await service.get_keywords(source)
    return {"source": source, "keywords": keywords}
