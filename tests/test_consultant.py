from app.services.ai import AIConsultant


def test_local_parser_understands_architectural_terms():
    consultant = AIConsultant()
    intent = consultant._parse_locally("Concrete for brutalist facade")
    assert intent.material_type == "concrete"
    assert intent.style == "brutalist"
    assert intent.usage == "facade"


def test_usage_recommendations_include_luxury_materials():
    consultant = AIConsultant()
    recommendations = consultant.recommendations_for_usage("floor", "luxury")
    assert "polished marble" in recommendations
    assert "terrazzo" in recommendations
