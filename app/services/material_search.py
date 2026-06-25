import asyncio
import hashlib
import logging
from collections.abc import Iterable

from rapidfuzz import fuzz

from app.core.config import settings
from app.services.ai import AIConsultant
from app.services.schemas import MaterialIntent, MaterialResult
from app.sources.base import MaterialSource

LOGGER = logging.getLogger(__name__)


class MaterialSearchService:
    def __init__(self, sources: Iterable[MaterialSource], consultant: AIConsultant) -> None:
        self.sources = list(sources)
        self.consultant = consultant
        self.cache: dict[str, MaterialResult] = {}

    async def search(self, text: str, usage: str | None = None) -> tuple[MaterialIntent, list[MaterialResult], str]:
        intent = await self.consultant.parse_intent(text, usage=usage)
        batches = await asyncio.gather(
            *(self._safe_source_search(source, intent) for source in self.sources),
            return_exceptions=False,
        )
        flattened = [result for batch in batches for result in batch]
        ranked = self._dedupe_and_rank(flattened, intent)[:6]
        for result in ranked:
            self.cache[self.short_id(result.key)] = result
        note = self.consultant.consultant_note(intent, len(ranked))
        return intent, ranked, note

    async def _safe_source_search(self, source: MaterialSource, intent: MaterialIntent) -> list[MaterialResult]:
        try:
            return await source.search(intent)
        except Exception as exc:
            LOGGER.warning("%s search failed: %s", source.name, exc)
            return [source.fallback_result(intent)]

    def _dedupe_and_rank(self, results: list[MaterialResult], intent: MaterialIntent) -> list[MaterialResult]:
        deduped: dict[str, MaterialResult] = {}
        query = intent.search_query.lower()
        query_tokens = {token for token in query.split() if len(token) > 2}
        for result in results:
            normalized = " ".join(
                f"{result.name} {result.category} {' '.join(result.recommended_usage)}"
                .lower()
                .replace("-", " ")
                .replace("_", " ")
                .split()
            )
            duplicate_key = normalized
            match_score = fuzz.token_set_ratio(query, normalized) / 100
            exact_bonus = 0.25 if query_tokens and query_tokens.issubset(set(normalized.split())) else 0
            usage_bonus = 0.08 if intent.usage and intent.usage in result.recommended_usage else 0
            direct_bonus = 0.2 if result.has_direct_downloads else 0
            preview_bonus = 0.05 if result.preview_url else 0
            fallback_penalty = -0.25 if result.name.endswith(f" on {result.source}") else 0
            result.score = max(result.score, match_score) + exact_bonus + usage_bonus + direct_bonus + preview_bonus + fallback_penalty
            if duplicate_key not in deduped or result.score > deduped[duplicate_key].score:
                deduped[duplicate_key] = result
        return sorted(deduped.values(), key=lambda item: item.score, reverse=True)

    def get_cached(self, key: str) -> MaterialResult | None:
        return self.cache.get(key)

    @staticmethod
    def short_id(key: str) -> str:
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]

    async def aclose(self) -> None:
        await asyncio.gather(*(source.aclose() for source in self.sources), return_exceptions=True)
