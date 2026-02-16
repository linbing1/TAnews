from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    title: str
    link: str
    summary: str
    published: datetime
    full_text: str = ""
    comment_count: int = 0


@dataclass
class AnalyzedArticle:
    title_cn: str
    title_original: str
    article_type: str
    importance: int
    overview: str
    detail: str
    key_people_and_data: str
    impact: str
    link: str
