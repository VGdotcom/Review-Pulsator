"""
Unit tests verifying Phase 1 Pydantic schema models.
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from review_pulsator.schemas import (
    RawReview,
    SanitizedReview,
    ThemeCluster,
    ThemeSummary,
    WeeklyPulseReport,
)


def test_raw_review_valid():
    review = RawReview(
        review_id="rev_101",
        store="apple_app_store",
        rating=5,
        title="Great App",
        body="Works seamlessly without crashing.",
        submitted_at=datetime.now(timezone.utc),
    )
    assert review.store == "APPLE_APP_STORE"
    assert review.rating == 5


def test_raw_review_invalid_store():
    with pytest.raises(ValidationError) as exc_info:
        RawReview(
            review_id="rev_102",
            store="INVALID_STORE",
            rating=4,
            title="Good",
            body="Nice app.",
            submitted_at=datetime.now(timezone.utc),
        )
    assert "Invalid store" in str(exc_info.value)


def test_raw_review_invalid_rating():
    with pytest.raises(ValidationError):
        RawReview(
            review_id="rev_103",
            store="GOOGLE_PLAY",
            rating=6,  # Invalid: > 5
            title="Too good",
            body="6 stars if I could.",
            submitted_at=datetime.now(timezone.utc),
        )


def test_sanitized_review_defaults():
    sanitized = SanitizedReview(
        review_id="rev_201",
        store="GOOGLE_PLAY",
        rating=3,
        title="Average",
        body="Needs improvement.",
        submitted_at=datetime.now(timezone.utc),
    )
    assert sanitized.is_pii_scrubbed is True
    assert sanitized.imputed_timestamp is False


def test_theme_cluster_valid():
    cluster = ThemeCluster(
        theme_id="theme_kyc",
        theme_name="KYC Verification",
        review_count=45,
        average_rating=1.8,
        rank=1,
        representative_quotes=["ID upload hangs at step 2."],
        sentiment_severity_score=81.0,
    )
    assert cluster.rank == 1
    assert len(cluster.representative_quotes) == 1


def test_weekly_pulse_report_valid():
    report = WeeklyPulseReport(
        report_date="2026-07-05",
        word_count=180,
        top_themes=[ThemeSummary(name="KYC", summary="ID upload hangs.")],
        verbatim_quotes=["ID upload hangs at step 2."],
        action_ideas=["Fix camera SDK focus bug."],
    )
    assert report.word_count == 180


def test_weekly_pulse_report_word_count_exceeded():
    with pytest.raises(ValidationError) as exc_info:
        WeeklyPulseReport(
            report_date="2026-07-05",
            word_count=251,  # Invalid: > 250
            top_themes=[ThemeSummary(name="KYC", summary="ID upload hangs.")],
            verbatim_quotes=["ID upload hangs at step 2."],
            action_ideas=["Fix camera SDK focus bug."],
        )
    assert "less than or equal to 250" in str(exc_info.value)
