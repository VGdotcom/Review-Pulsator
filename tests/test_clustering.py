"""
Unit tests for Phase 3 Clustering & Theming Engine (ThemingEngine).
Verifies taxonomy mapping, ranking formula, noise filtering, and edge cases.
"""
import pytest
from datetime import datetime, timezone
from review_pulsator.schemas import SanitizedReview, ThemeCluster
from review_pulsator.clustering import ThemingEngine


@pytest.fixture
def sample_reviews():
    now = datetime.now(timezone.utc)
    return [
        # Delivery complaints (3 reviews, 1-star average)
        SanitizedReview(
            review_id="rev_1",
            store="GOOGLE_PLAY",
            user_name="Rahul",
            rating=1,
            title="Cold food and 50 mins late",
            body="My order arrived almost an hour late during dinner rush. Delivery executive GPS tracking was stuck.",
            submitted_at=now,
        ),
        SanitizedReview(
            review_id="rev_2",
            store="APPLE_APP_STORE",
            user_name="Priya",
            rating=1,
            title="Delivery partner behavior",
            body="The delivery partner refused to come up in the elevator and left the food at the gate. Very rude behavior.",
            submitted_at=now,
        ),
        SanitizedReview(
            review_id="rev_3",
            store="GOOGLE_PLAY",
            user_name="Amit",
            rating=1,
            title="Late delivery again",
            body="Always late by 30 minutes. Delivery boy never calls when arriving.",
            submitted_at=now,
        ),
        # App performance (2 reviews, 2-star average)
        SanitizedReview(
            review_id="rev_4",
            store="GOOGLE_PLAY",
            user_name="John",
            rating=2,
            title="App crashes on checkout",
            body="The app freezes and crashes every time I try to pay via UPI on the payment screen.",
            submitted_at=now,
        ),
        SanitizedReview(
            review_id="rev_5",
            store="GOOGLE_PLAY",
            user_name="Sara",
            rating=2,
            title="Login bug",
            body="Cannot login after latest update. App hangs endlessly on splash screen.",
            submitted_at=now,
        ),
        # Pricing / Support (1 review, 1-star)
        SanitizedReview(
            review_id="rev_6",
            store="APPLE_APP_STORE",
            user_name="Mike",
            rating=1,
            title="Refund denied by chat bot",
            body="Customer support chat closed without refunding for missing burger. Swiggy One membership is a scam.",
            submitted_at=now,
        ),
        # Noise / Generic praise (should be filtered or ranked lower)
        SanitizedReview(
            review_id="rev_7",
            store="GOOGLE_PLAY",
            user_name="User1",
            rating=5,
            title="good",
            body="good",
            submitted_at=now,
        ),
        SanitizedReview(
            review_id="rev_8",
            store="GOOGLE_PLAY",
            user_name="User2",
            rating=5,
            title="nice app",
            body="nice app",
            submitted_at=now,
        ),
    ]


def test_empty_reviews_clustering():
    engine = ThemingEngine()
    clusters = engine.cluster_reviews([])
    assert len(clusters) == 1
    assert clusters[0].theme_id == "theme_empty"
    assert clusters[0].theme_name == "No Volume"
    assert clusters[0].review_count == 0


def test_taxonomy_mapping_and_scoring(sample_reviews):
    engine = ThemingEngine()
    clusters = engine.cluster_reviews(sample_reviews)
    
    # Must group into <= 5 themes
    assert len(clusters) <= 5
    
    # The delivery cluster should be rank 1 due to highest volume (3) and severe rating (1.0)
    top_cluster = clusters[0]
    assert top_cluster.rank == 1
    assert top_cluster.theme_id == "theme_delivery"
    assert top_cluster.review_count == 3
    assert top_cluster.average_rating == 1.0
    
    # Verify score formula: 3 * ((5.0 - 1.0)*10.0 + 1.0) = 3 * 41.0 = 123.0
    expected_score = round(3 * 41.0, 2)
    assert top_cluster.sentiment_severity_score == expected_score


def test_representative_quotes_verbatim(sample_reviews):
    engine = ThemingEngine()
    clusters = engine.cluster_reviews(sample_reviews)
    
    for clu in clusters:
        for quote in clu.representative_quotes:
            # Must be an exact substring of one of the original review bodies
            matching_review = any(quote in r.body for r in sample_reviews)
            assert matching_review is True, f"Quote '{quote}' was not found verbatim in any review body."


def test_noise_filtering(sample_reviews):
    engine = ThemingEngine()
    
    # Just noise reviews
    noise_only = [
        SanitizedReview(review_id="n1", store="GOOGLE_PLAY", rating=5, title="good", body="good", submitted_at=datetime.now(timezone.utc)),
        SanitizedReview(review_id="n2", store="GOOGLE_PLAY", rating=5, title="nice app", body="nice app", submitted_at=datetime.now(timezone.utc)),
    ]
    clusters = engine.cluster_reviews(noise_only)
    assert len(clusters) > 0
    # When combined with real reviews, noise shouldn't overtake high severity themes
    all_clusters = engine.cluster_reviews(sample_reviews)
    assert all_clusters[0].theme_id != "theme_noise"


def test_low_cluster_density_padding():
    engine = ThemingEngine()
    single_review = [
        SanitizedReview(
            review_id="rev_single",
            store="GOOGLE_PLAY",
            rating=1,
            title="App crash",
            body="The app crashes on startup every single time.",
            submitted_at=datetime.now(timezone.utc),
        )
    ]
    clusters = engine.cluster_reviews(single_review)
    assert len(clusters) == 1
    
    # get_top_themes should pad to exactly 3 themes
    top_3 = engine.get_top_themes(clusters, count=3)
    assert len(top_3) == 3
    assert top_3[0].theme_id == "theme_app"
    assert "theme_pad_" in top_3[1].theme_id
    assert "theme_pad_" in top_3[2].theme_id
