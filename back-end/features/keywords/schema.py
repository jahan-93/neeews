from pydantic import BaseModel


class KeywordItem(BaseModel):
    keyword: str
    count: int


class KeywordsResponse(BaseModel):
    source: str
    keywords: list[KeywordItem]
