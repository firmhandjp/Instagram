from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    source: str
    summary: str
    published: datetime  # タイムゾーン付き


@dataclass(frozen=True)
class Draft:
    headline: str
    caption: str
    article_url: str
    source: str
    date: str  # JST の YYYY-MM-DD

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> Draft:
        return cls(**json.loads(text))
