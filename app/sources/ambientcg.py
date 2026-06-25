from app.services.schemas import MaterialIntent, MaterialResult
from app.sources.base import MaterialSource


class AmbientCGSource(MaterialSource):
    name = "AmbientCG"
    base_url = "https://ambientcg.com"

    def search_url(self, query: str) -> str:
        return f"{self.base_url}/list?search={query}"

    async def search(self, intent: MaterialIntent) -> list[MaterialResult]:
        response = await self.client.get(f"{self.base_url}/api/v2/full_json", params={"q": intent.search_query})
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("foundAssets", [])[:5]:
            asset_id = item.get("assetId") or item.get("assetID")
            if not asset_id:
                continue
            category = item.get("category") or intent.material_type or "material"
            page_url = f"{self.base_url}/view?id={asset_id}"
            preview = f"https://ambientcg.com/get?file={asset_id}_Preview.jpg"
            downloads = {
                quality: f"https://ambientcg.com/get?file={asset_id}_{quality}-JPG.zip"
                for quality in ["1K", "2K", "4K", "8K"]
            }
            map_downloads = {
                quality: {
                    "diffuse": f"https://ambientcg.com/get?file={asset_id}_{quality}-JPG_Color.jpg",
                    "normal": f"https://ambientcg.com/get?file={asset_id}_{quality}-JPG_NormalGL.jpg",
                    "roughness": f"https://ambientcg.com/get?file={asset_id}_{quality}-JPG_Roughness.jpg",
                    "displacement": f"https://ambientcg.com/get?file={asset_id}_{quality}-JPG_Displacement.jpg",
                    "ao": f"https://ambientcg.com/get?file={asset_id}_{quality}-JPG_AmbientOcclusion.jpg",
                    "zip": downloads[quality],
                }
                for quality in ["1K", "2K", "4K", "8K"]
            }
            results.append(
                MaterialResult(
                    key=f"ambientcg:{asset_id}",
                    source=self.name,
                    name=item.get("displayName") or asset_id,
                    category=category,
                    recommended_usage=[intent.usage] if intent.usage else ["interior", "3D visualization"],
                    resolution="1K-8K",
                    preview_url=preview,
                    page_url=page_url,
                    download_url=page_url,
                    downloads=downloads,
                    map_downloads=map_downloads,
                    similar=[],
                    score=1.0,
                )
            )
        return results or [self.fallback_result(intent)]
