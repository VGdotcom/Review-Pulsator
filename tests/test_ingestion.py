"""
Unit tests verifying ingestion service, time-window filtering, and spam rejection.
"""
import csv
import json
import pytest
from datetime import datetime, timezone, timedelta
from review_pulsator.config import PulsatorConfig
from review_pulsator.ingestion import IngestionService


@pytest.fixture
def sample_reference_date():
    return datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def test_load_csv_filtering(tmp_path, sample_reference_date):
    csv_file = tmp_path / "reviews.csv"
    
    # Dates relative to reference date (2026-07-05)
    valid_date = (sample_reference_date - timedelta(weeks=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old_date = (sample_reference_date - timedelta(weeks=16)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    rows = [
        ["review_id", "store", "user_name", "rating", "title", "body", "submitted_at"],
        ["rev_1", "GOOGLE_PLAY", "Rahul Sharma", "1", "Crash", "App crashes on startup when clicking login.", valid_date],
        ["rev_2", "GOOGLE_PLAY", "Priya", "5", "Old", "Great app works well.", old_date],  # Rejected: outside window
        ["rev_3", "APPLE_APP_STORE", "Amit", "1", "Spam", "!!??", valid_date],  # Rejected: < 3 alnum chars
    ]
    
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
        
    service = IngestionService()
    results = service.load_reviews_from_file(str(csv_file), reference_date=sample_reference_date)
    
    assert len(results) == 1
    assert results[0].review_id == "rev_1"
    assert results[0].store == "GOOGLE_PLAY"
    assert results[0].user_name == "Rahul Sharma"
    assert results[0].is_pii_scrubbed is True
    assert results[0].imputed_timestamp is False


def test_load_json_with_pii(tmp_path, sample_reference_date):
    json_file = tmp_path / "reviews.json"
    valid_date = (sample_reference_date - timedelta(weeks=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    data = [
        {
            "review_id": "rev_101",
            "store": "APPLE_APP_STORE",
            "user_name": "user@gmail.com",
            "rating": 2,
            "title": "KYC failed for john@example.com",
            "body": "Call me at +1 555-0199 to fix this bug on iOS.",
            "submitted_at": valid_date,
        }
    ]
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    service = IngestionService()
    results = service.load_reviews_from_file(str(json_file), reference_date=sample_reference_date)
    
    assert len(results) == 1
    review = results[0]
    assert "[ANONYMIZED_EMAIL]" in review.user_name
    assert "john@example.com" not in review.title
    assert "[ANONYMIZED_EMAIL]" in review.title
    assert "555-0199" not in review.body
    assert "[ANONYMIZED_PHONE]" in review.body
    assert "iOS" in review.body  # Whitelisted term preserved


def test_imputed_timestamp(tmp_path, sample_reference_date):
    json_file = tmp_path / "malformed.json"
    data = [
        {
            "review_id": "rev_201",
            "store": "GOOGLE_PLAY",
            "rating": 4,
            "title": "Good app",
            "body": "Needs dark mode in statement view.",
            "submitted_at": "",  # Missing timestamp
        }
    ]
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    service = IngestionService()
    results = service.load_reviews_from_file(str(json_file), reference_date=sample_reference_date)
    
    assert len(results) == 1
    assert results[0].imputed_timestamp is True
    expected_dt = sample_reference_date - timedelta(weeks=10)
    assert results[0].submitted_at == expected_dt


def test_data_normalization_rules(tmp_path, sample_reference_date):
    json_file = tmp_path / "normalized_reviews.json"
    valid_date = (sample_reference_date - timedelta(weeks=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    data = [
        # 1. Hindi review (Devanagari) -> Should be ignored
        {
            "review_id": "rev_hindi_1",
            "store": "GOOGLE_PLAY",
            "rating": 1,
            "title": "बकवास ऐप",
            "body": "खाना बहुत देर से आया और कोई रिफंड नहीं मिला।",
            "submitted_at": valid_date,
        },
        # 2. Hindi review (Hinglish) -> Should be ignored
        {
            "review_id": "rev_hindi_2",
            "store": "GOOGLE_PLAY",
            "rating": 1,
            "title": "Bahut bekar service",
            "body": "Bhai swiggy ka delivery agent nahi aya, paisa waste ho gaya mera.",
            "submitted_at": valid_date,
        },
        # 3. Review with Emojis -> Should be kept but Emojis stripped
        {
            "review_id": "rev_emoji_valid",
            "store": "GOOGLE_PLAY",
            "rating": 2,
            "title": "😡😡 Late delivery again!!",
            "body": "My food order arrived 50 mins late and cold 🍕🍕🍕!! Fix your GPS tracking.",
            "submitted_at": valid_date,
        },
        # 4. Review with unclear meaning / generic noise -> Should be removed
        {
            "review_id": "rev_unclear_1",
            "store": "GOOGLE_PLAY",
            "rating": 5,
            "title": "osm",
            "body": "nice app",
            "submitted_at": valid_date,
        },
        # 5. Review with gibberish -> Should be removed
        {
            "review_id": "rev_unclear_2",
            "store": "GOOGLE_PLAY",
            "rating": 1,
            "title": "xxxx",
            "body": "asdfghjkl",
            "submitted_at": valid_date,
        }
    ]
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    service = IngestionService()
    results = service.load_reviews_from_file(str(json_file), reference_date=sample_reference_date)
    
    # Only rev_emoji_valid should remain!
    assert len(results) == 1
    assert results[0].review_id == "rev_emoji_valid"
    # Verify emojis were stripped cleanly
    assert "😡" not in results[0].title
    assert "🍕" not in results[0].body
    assert results[0].title == "Late delivery again!!"
    assert results[0].body == "My food order arrived 50 mins late and cold !! Fix your GPS tracking."
