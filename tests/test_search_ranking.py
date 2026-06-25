from app.services.ai import AIConsultant
from app.services.material_search import MaterialSearchService
from app.services.schemas import MaterialIntent, MaterialResult


def test_dedupe_and_rank_prefers_relevant_result():
    service = MaterialSearchService([], AIConsultant())
    intent = MaterialIntent(raw_text="walnut wood", material_type="walnut")
    results = [
        MaterialResult(
            key="a",
            source="x",
            name="blue fabric",
            category="fabric",
            recommended_usage=["interior"],
            resolution="1K",
            preview_url=None,
            page_url="https://x",
            download_url=None,
        ),
        MaterialResult(
            key="b",
            source="x",
            name="walnut wood planks",
            category="wood",
            recommended_usage=["interior"],
            resolution="4K",
            preview_url=None,
            page_url="https://x",
            download_url=None,
            downloads={"2K": "https://x/file.zip"},
        ),
    ]
    ranked = service._dedupe_and_rank(results, intent)
    assert ranked[0].name == "walnut wood planks"
