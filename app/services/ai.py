import json
import logging
import re

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.schemas import MaterialIntent

LOGGER = logging.getLogger(__name__)

MATERIAL_TYPES = [
    "wood",
    "oak",
    "walnut",
    "concrete",
    "marble",
    "stone",
    "brick",
    "metal",
    "fabric",
    "leather",
    "glass",
    "tile",
    "terrazzo",
    "plaster",
    "limestone",
    "travertine",
    "granite",
]
COLORS = [
    "white",
    "black",
    "dark",
    "light",
    "grey",
    "gray",
    "gold",
    "golden",
    "brown",
    "red",
    "green",
    "blue",
    "beige",
    "cream",
]
FINISHES = ["polished", "matte", "rough", "brushed", "glossy", "burned", "aged", "raw", "exposed"]
STYLES = ["minimalist", "industrial", "scandinavian", "brutalist", "contemporary", "luxury", "rustic"]
USAGES = ["floor", "wall", "roof", "door", "ceiling", "furniture", "exterior", "interior", "facade"]

USAGE_RECOMMENDATIONS: dict[str, list[str]] = {
    "floor": ["polished marble", "terrazzo", "porcelain tile", "engineered oak", "large stone slabs"],
    "wall": ["lime plaster", "travertine", "microcement", "brick", "fluted wood panels"],
    "roof": ["standing seam metal", "terracotta tile", "slate", "concrete roof tile"],
    "door": ["solid oak", "walnut veneer", "brushed metal", "painted timber"],
    "ceiling": ["acoustic wood slats", "painted gypsum", "exposed concrete", "linear metal panels"],
    "furniture": ["walnut wood", "oak veneer", "boucle fabric", "brushed brass", "leather"],
    "exterior": ["limestone", "travertine", "exposed concrete", "brick", "fiber cement panels"],
    "interior": ["oak wood", "microcement", "marble", "terrazzo", "textured plaster"],
    "facade": ["travertine", "limestone", "brick", "exposed concrete", "zinc panels"],
}


class AIConsultant:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def parse_intent(self, text: str, usage: str | None = None) -> MaterialIntent:
        if self.client:
            try:
                return await self._parse_with_openai(text=text, usage=usage)
            except Exception:
                LOGGER.exception("OpenAI intent parsing failed; falling back to local parser")
        return self._parse_locally(text=text, usage=usage)

    async def _parse_with_openai(self, text: str, usage: str | None) -> MaterialIntent:
        system = (
            "Extract architectural material search intent. Return compact JSON with keys: "
            "material_type, color, finish, style, usage, surface_properties, environment."
        )
        response = await self.client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Text: {text}\nKnown usage: {usage or ''}"},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return MaterialIntent(
            raw_text=text,
            material_type=data.get("material_type"),
            color=data.get("color"),
            finish=data.get("finish"),
            style=data.get("style"),
            usage=data.get("usage") or usage,
            surface_properties=data.get("surface_properties") or [],
            environment=data.get("environment"),
        )

    def _parse_locally(self, text: str, usage: str | None = None) -> MaterialIntent:
        lowered = text.lower()

        def first_match(values: list[str]) -> str | None:
            return next((value for value in values if re.search(rf"\b{re.escape(value)}\b", lowered)), None)

        properties = [
            word
            for word in ["veined", "grain", "speckled", "porous", "smooth", "seamless", "weathered"]
            if word in lowered
        ]
        return MaterialIntent(
            raw_text=text,
            material_type=first_match(MATERIAL_TYPES),
            color=first_match(COLORS),
            finish=first_match(FINISHES),
            style=first_match(STYLES),
            usage=usage or first_match(USAGES),
            surface_properties=properties,
            environment="exterior" if "outdoor" in lowered or "exterior" in lowered else None,
        )

    def recommendations_for_usage(self, usage: str, style: str | None = None) -> list[str]:
        suggestions = list(USAGE_RECOMMENDATIONS.get(usage.lower(), []))
        if style == "brutalist":
            suggestions[:0] = ["board-formed concrete", "exposed aggregate concrete"]
        if style == "luxury":
            suggestions[:0] = ["polished marble", "bookmatched stone", "brushed brass inlay"]
        if style == "industrial":
            suggestions[:0] = ["exposed concrete", "blackened steel", "reclaimed brick"]
        return list(dict.fromkeys(suggestions))

    def consultant_note(self, intent: MaterialIntent, count: int) -> str:
        usage = f" for {intent.usage}" if intent.usage else ""
        style = f" with a {intent.style} character" if intent.style else ""
        if count:
            return (
                f"I found {count} material options{usage}{style}. I prioritized free PBR sources, "
                "practical architectural use, and visual fit."
            )
        recommendations = self.recommendations_for_usage(intent.usage or "interior", intent.style)
        return (
            "I could not confirm direct matches from the sources right now. As a consultant, I would "
            f"start with: {', '.join(recommendations[:4])}."
        )
