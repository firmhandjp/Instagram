from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Feed:
    name: str
    url: str


@dataclass(frozen=True)
class Config:
    feeds: list[Feed]
    lookback_hours: int
    max_candidates: int
    model: str
    image_width: int
    image_height: int


def load_config(path: Path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    news = raw["news"]
    return Config(
        feeds=[Feed(x["name"], x["url"]) for x in news["feeds"]],
        lookback_hours=news["lookback_hours"],
        max_candidates=news["max_candidates"],
        model=raw["claude"]["model"],
        image_width=raw["image"]["width"],
        image_height=raw["image"]["height"],
    )
