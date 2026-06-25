from app.services.schemas import MaterialIntent, MaterialResult
from app.sources.base import MaterialSource


class PolyHavenSource(MaterialSource):
    name = "Poly Haven"
    base_url = "https://polyhaven.com"

    def search_url(self, query: str) -> str:
        return f"{self.base_url}/textures?search={query}"

    async def search(self, intent: MaterialIntent) -> list[MaterialResult]:
        response = await self.client.get(f"{self.base_url}/api/assets", params={"type": "textures"})
        response.raise_for_status()
        data = response.json()
        tokens = {part.lower() for part in intent.search_query.split()}
        results = []
        for slug, item in data.items():
            haystack = f"{slug} {item.get('name', '')} {' '.join(item.get('categories', []))}".lower()
            if tokens and not any(token in haystack for token in tokens):
                continue
            page_url = f"{self.base_url}/a/{slug}"
            results.append(
                MaterialResult(
                    key=f"polyhaven:{slug}",
                    source=self.name,
                    name=item.get("name") or slug.replace("_", " ").title(),
                    category=", ".join(item.get("categories", [])[:2]) or intent.material_type or "texture",
                    recommended_usage=[intent.usage] if intent.usage else ["visualization", "interior"],
                    resolution="1K-8K",
                    preview_url=f"https://cdn.polyhaven.com/asset_img/primary/{slug}.png?height=256",
                    page_url=page_url,
                    download_url=page_url,
                    downloads={},
                    similar=[],
                    score=0.85,
                )
            )
            if len(results) >= 5:
                break
        return results or [self.fallback_result(intent)]
