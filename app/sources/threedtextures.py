from bs4 import BeautifulSoup

from app.services.schemas import MaterialIntent, MaterialResult
from app.sources.base import MaterialSource


class ThreeDTexturesSource(MaterialSource):
    name = "3DTextures"
    base_url = "https://3dtextures.me"

    def search_url(self, query: str) -> str:
        return f"{self.base_url}/?s={query}"

    async def search(self, intent: MaterialIntent) -> list[MaterialResult]:
        response = await self.client.get(self.search_url(intent.search_query))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for article in soup.select("article")[:5]:
            link = article.select_one("a[href]")
            title = article.select_one("h2, h3, .entry-title")
            if not link:
                continue
            href = link.get("href")
            page_url = href if href and href.startswith("http") else f"{self.base_url}{href}"
            results.append(
                MaterialResult(
                    key=f"3dtextures:{page_url}",
                    source=self.name,
                    name=(title.get_text(" ", strip=True) if title else intent.search_query.title())[:100],
                    category=intent.material_type or "material",
                    recommended_usage=[intent.usage] if intent.usage else ["visualization"],
                    resolution="1K-4K",
                    preview_url=None,
                    page_url=page_url,
                    download_url=page_url,
                    similar=[],
                    score=0.6,
                )
            )
        return results or [self.fallback_result(intent)]
