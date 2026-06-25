from bs4 import BeautifulSoup

from app.services.schemas import MaterialIntent, MaterialResult
from app.sources.base import MaterialSource


class CGBookcaseSource(MaterialSource):
    name = "CGBookcase"
    base_url = "https://www.cgbookcase.com"

    def search_url(self, query: str) -> str:
        return f"{self.base_url}/textures/?search={query}"

    async def search(self, intent: MaterialIntent) -> list[MaterialResult]:
        response = await self.client.get(self.search_url(intent.search_query))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("a[href*='/textures/']")[:8]
        results = []
        seen = set()
        for card in cards:
            href = card.get("href")
            title = card.get_text(" ", strip=True)
            if not href or not title or href in seen:
                continue
            seen.add(href)
            page_url = href if href.startswith("http") else f"{self.base_url}{href}"
            results.append(
                MaterialResult(
                    key=f"cgbookcase:{href}",
                    source=self.name,
                    name=title[:100],
                    category=intent.material_type or "texture",
                    recommended_usage=[intent.usage] if intent.usage else ["PBR rendering"],
                    resolution="1K-4K",
                    preview_url=None,
                    page_url=page_url,
                    download_url=page_url,
                    similar=[],
                    score=0.7,
                )
            )
            if len(results) >= 5:
                break
        return results or [self.fallback_result(intent)]
