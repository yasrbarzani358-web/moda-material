from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import settings


class DownloadTooLargeError(RuntimeError):
    pass


class MaterialDownloader:
    def __init__(self) -> None:
        self.output_dir = settings.generated_dir / "downloads"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def fetch_zip(self, url: str, filename: str) -> Path:
        return await self.fetch_file(url, filename, max_mb=settings.max_bot_download_mb)

    async def fetch_preview(self, url: str, filename: str) -> Path:
        return await self.fetch_file(url, filename, max_mb=8)

    async def fetch_file(self, url: str, filename: str, max_mb: int) -> Path:
        safe_name = self._safe_filename(filename)
        target = self.output_dir / safe_name
        max_bytes = max_mb * 1024 * 1024

        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", url, headers={"User-Agent": "AI Material Assistant/1.0"}) as response:
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    raise DownloadTooLargeError(f"File is larger than {max_mb} MB")

                total = 0
                with target.open("wb") as file:
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            file.close()
                            target.unlink(missing_ok=True)
                            raise DownloadTooLargeError(f"File is larger than {max_mb} MB")
                        file.write(chunk)

        return target

    def _safe_filename(self, filename: str) -> str:
        parsed = Path(urlparse(filename).path).name if filename.startswith("http") else filename
        safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in parsed)
        return safe[:120] or "material.zip"
