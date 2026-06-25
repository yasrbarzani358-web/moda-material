from bs4 import BeautifulSoup

from app.services.schemas import MaterialIntent, MaterialResult
from app.sources.base import MaterialSource


class TextureCanSource(MaterialSource):
    name = "TextureCan"
    base_url = "https://www.texturecan.com"

    def search_url(self, query: str) -> str:
        return f"{self.base_url}/search/?q={query}"

    async def search(self, intent: MaterialIntent) -> list[MaterialResult]:
        response = await self.client.get(self.search_url(intent.search_query))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        for link in soup.select("a[href*='/details/']")[:5]:
            href = link.get("href")
            name = link.get_text(" ", strip=True) or intent.search_query.title()
            if not href:
                continue
            page_url = href if href.startswith("http") else f"{self.base_url}{href}"
            results.append(
                MaterialResult(
                    key=f"texturecan:{href}",
                    source=self.name,
                    name=name[:100],
                    category=intent.material_type or "material",
                    recommended_usage=[intent.usage] if intent.usage else ["3D rendering"],
                    resolution="1K-4K",
                    preview_url=None,
                    page_url=page_url,
                    download_url=page_url,
                    similar=[],
                    score=0.65,
                )
            )
        return results or [self.fallback_result(intent)]
