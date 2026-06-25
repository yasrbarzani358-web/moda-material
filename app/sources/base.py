from abc import ABC, abstractmethod
from urllib.parse import quote_plus

import httpx

from app.core.config import settings
from app.services.schemas import MaterialIntent, MaterialResult


class MaterialSource(ABC):
    name: str
    base_url: str

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "AI Material Assistant/1.0"},
        )

    @abstractmethod
    async def search(self, intent: MaterialIntent) -> list[MaterialResult]:
        raise NotImplementedError

    async def aclose(self) -> None:
        await self.client.aclose()

    def fallback_result(self, intent: MaterialIntent, category: str = "material") -> MaterialResult:
        query = quote_plus(intent.search_query)
        page_url = self.search_url(query)
        return MaterialResult(
            key=f"{self.name}:{query}",
            source=self.name,
            name=f"{intent.search_query.title()} on {self.name}",
            category=category,
            recommended_usage=[intent.usage] if intent.usage else ["interior", "architectural visualization"],
            resolution="varies",
            preview_url=None,
            page_url=page_url,
            download_url=page_url,
            similar=[],
            score=0.35,
        )

    def search_url(self, query: str) -> str:
        return f"{self.base_url}/?s={query}"
