from pydantic import BaseModel


class ArticleResponse(BaseModel):
    title: str
    link: str
    source: str
    category: str
    pub_date: str
    image_url: str | None
    description: str
    paragraphs: list[str]


class NewsListResponse(BaseModel):
    source: str
    articles: list[ArticleResponse]
