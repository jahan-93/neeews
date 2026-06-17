from pydantic import BaseModel


class ArticleResponse(BaseModel):
    title: str
    link: str
    category: str
    pub_date: str
    image_url: str | None
    description: str
    paragraphs: list[str]


class NewsListResponse(BaseModel):
    category: str
    articles: list[ArticleResponse]
