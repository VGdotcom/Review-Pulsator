"""
Unit tests for Phase 4 Pulse Synthesis & Summarization Module (PulseGenerator).
Verifies word count calculation, verbatim quote validation, clause pruning,
and offline/deterministic fallback synthesis.
"""
import pytest
from unittest.mock import MagicMock, patch
from review_pulsator.schemas import ThemeCluster, WeeklyPulseReport
from review_pulsator.synthesis import PulseGenerator


@pytest.fixture
def sample_top_themes():
    return [
        ThemeCluster(
            theme_id="theme_pricing",
            theme_name="Pricing, Refund & Customer Support",
            review_count=93,
            average_rating=2.14,
            rank=1,
            representative_quotes=[
                "Absolutely pathetic service from Swiggy",
                "I have been using Swiggy for the past 12 years, but this has been my worst experience"
            ],
            sentiment_severity_score=2752.8,
        ),
        ThemeCluster(
            theme_id="theme_delivery",
            theme_name="Delivery Speed & Partner Behavior",
            review_count=87,
            average_rating=2.26,
            rank=2,
            representative_quotes=[
                "it was showing price Rs 320 but I had to pay 393",
                "Very disappointed with the Swiggy delivery and customer service"
            ],
            sentiment_severity_score=2470.8,
        ),
        ThemeCluster(
            theme_id="theme_app",
            theme_name="App Performance & Usability",
            review_count=114,
            average_rating=4.34,
            rank=3,
            representative_quotes=[
                "it's not an good app",
                "The user treatment is getting worse by the day"
            ],
            sentiment_severity_score=866.4,
        ),
    ]


def test_word_count_calculation():
    generator = PulseGenerator()
    payload = {
        "report_date": "2026-07-05",
        "top_themes": [
            {"name": "Theme A", "summary": "This is a brief summary."},
            {"name": "Theme B", "summary": "Another short sentence here."}
        ],
        "verbatim_quotes": ["Quote number one is good.", "Quote number two is fine."],
        "action_ideas": ["Fix bug X immediately."]
    }
    # Count words across all values
    words = generator._calculate_word_count(payload)
    assert words > 10
    assert words < 50


def test_quote_verification_pass_and_fail():
    generator = PulseGenerator()
    valid_set = {
        "Absolutely pathetic service from Swiggy",
        "it was showing price Rs 320 but I had to pay 393",
        "it's not an good app"
    }
    
    # Valid quotes
    is_valid, err = generator._verify_quotes(list(valid_set), valid_set)
    assert is_valid is True
    assert err is None
    
    # Paraphrased / Hallucinated quote (Edge-case 4.2)
    fake_quotes = [
        "Absolutely pathetic service from Swiggy",
        "it was showing price Rs 320 but I had to pay 393",
        "it is not a good app"  # 'is not a good app' instead of 'it\'s not an good app'
    ]
    is_valid, err = generator._verify_quotes(fake_quotes, valid_set)
    assert is_valid is False
    assert "failed verbatim verification" in err


def test_prune_to_word_ceiling():
    generator = PulseGenerator()
    long_summary = "word " * 60
    long_action = "do something " * 40
    payload = {
        "report_date": "2026-07-05",
        "top_themes": [
            {"name": "Theme A", "summary": long_summary},
            {"name": "Theme B", "summary": long_summary},
            {"name": "Theme C", "summary": long_summary},
        ],
        "verbatim_quotes": ["Quote 1", "Quote 2", "Quote 3"],
        "action_ideas": [long_action, long_action, long_action],
    }
    
    initial_words = generator._calculate_word_count(payload)
    assert initial_words > 300
    
    pruned = generator._prune_to_word_ceiling(payload, max_words=240)
    final_words = pruned["word_count"]
    assert final_words <= 245
    assert len(pruned["top_themes"]) == 3
    assert len(pruned["action_ideas"]) == 3


def test_deterministic_fallback_synthesis(sample_top_themes):
    # Initialize without API key to trigger offline fallback
    generator = PulseGenerator(api_key="")
    report = generator.generate_pulse(sample_top_themes, report_date="2026-07-05")
    
    assert isinstance(report, WeeklyPulseReport)
    assert report.report_date == "2026-07-05"
    assert report.word_count <= 250
    assert len(report.top_themes) == 3
    assert len(report.verbatim_quotes) == 3
    assert len(report.action_ideas) == 3
    
    # All quotes in fallback must be from the source clusters
    all_source_quotes = [q for c in sample_top_themes for q in c.representative_quotes]
    for rq in report.verbatim_quotes:
        assert rq in all_source_quotes


def test_mock_groq_synthesis_retry(sample_top_themes):
    generator = PulseGenerator(api_key="mock_key", max_retries=1)
    
    # Mock Groq client
    mock_client = MagicMock()
    generator.client = mock_client
    
    # 1st response: Hallucinated quote
    resp_1 = MagicMock()
    resp_1.choices = [MagicMock()]
    resp_1.choices[0].message.content = '{"report_date": "2026-07-05", "word_count": 50, "top_themes": [{"name": "P1", "summary": "S1"}, {"name": "P2", "summary": "S2"}, {"name": "P3", "summary": "S3"}], "verbatim_quotes": ["Fake quote 1", "Absolutely pathetic service from Swiggy", "it\'s not an good app"], "action_ideas": ["A1", "A2", "A3"]}'
    
    # 2nd response: Valid quotes
    resp_2 = MagicMock()
    resp_2.choices = [MagicMock()]
    resp_2.choices[0].message.content = '{"report_date": "2026-07-05", "word_count": 50, "top_themes": [{"name": "P1", "summary": "S1"}, {"name": "P2", "summary": "S2"}, {"name": "P3", "summary": "S3"}], "verbatim_quotes": ["Very disappointed with the Swiggy delivery and customer service", "Absolutely pathetic service from Swiggy", "it\'s not an good app"], "action_ideas": ["A1", "A2", "A3"]}'
    
    mock_client.chat.completions.create.side_effect = [resp_1, resp_2]
    
    report = generator.generate_pulse(sample_top_themes, report_date="2026-07-05")
    
    assert mock_client.chat.completions.create.call_count == 2
    assert isinstance(report, WeeklyPulseReport)
    assert "Very disappointed with the Swiggy delivery" in report.verbatim_quotes[0]
