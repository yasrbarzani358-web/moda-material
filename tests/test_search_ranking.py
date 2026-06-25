from app.services.ai import AIConsultant
from app.services.material_search import MaterialSearchService
from app.services.schemas import MaterialIntent, MaterialResult


def test_dedupe_and_rank_prefers_relevant_result():
    service = MaterialSearchService([], AIConsultant())
    intent = MaterialIntent(raw_text="walnut wood", material_type="walnut")
    results = [
        MaterialResult("a", "x", "blue fabric", "fabric", ["interior"], "1K", None, "https://x", None),
        MaterialResult("b", "x", "walnut wood planks", "wood", ["interior"], "4K", None, "https://x", None),
    ]
    ranked = service._dedupe_and_rank(results, intent)
    assert ranked[0].name == "walnut wood planks"
