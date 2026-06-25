from dataclasses import dataclass, field


@dataclass(slots=True)
class MaterialIntent:
    raw_text: str
    material_type: str | None = None
    color: str | None = None
    finish: str | None = None
    style: str | None = None
    usage: str | None = None
    surface_properties: list[str] = field(default_factory=list)
    environment: str | None = None

    @property
    def search_query(self) -> str:
        parts = [
            self.color,
            self.finish,
            self.material_type,
            self.style,
            self.usage,
            *self.surface_properties,
        ]
        return " ".join(part for part in parts if part).strip() or self.raw_text


@dataclass(slots=True)
class MaterialResult:
    key: str
    source: str
    name: str
    category: str
    recommended_usage: list[str]
    resolution: str | None
    preview_url: str | None
    page_url: str
    download_url: str | None
    similar: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass(slots=True)
class GeneratedMaterialPackage:
    prompt: str
    directory: str
    maps: dict[str, str]
    notes: str
