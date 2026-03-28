from app.agents.mandate_agent.gap_analyzer import analyze_mandate_gaps


def test_analyze_mandate_gaps_asks_vehicle_specific_clarifier():
    gap_info = analyze_mandate_gaps(
        {
            "intent_type": "buy",
            "vertical": "goods",
            "category": "car",
        }
    )

    assert gap_info["next_gap"] == "category_detail"
    assert "sedan or suv" in gap_info["next_question"].lower()


def test_analyze_mandate_gaps_skips_category_detail_when_style_exists():
    gap_info = analyze_mandate_gaps(
        {
            "intent_type": "buy",
            "vertical": "goods",
            "category": "car",
            "style_preferences": ["suv"],
        }
    )

    assert gap_info["next_gap"] == "budget"
