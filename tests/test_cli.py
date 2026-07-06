"""
Unit tests for Review Pulsator CLI and E2E Pipeline Orchestrator (Phase 6).
"""
import os
import json
import tempfile
from unittest.mock import patch
from datetime import datetime, timezone
from review_pulsator.cli import run_pipeline
from review_pulsator.config import PulsatorConfig


def test_cli_dry_run_pipeline(tmp_path):
    """Test full E2E pipeline in dry-run mode using synthetic input dataset."""
    sample_data = [
        {
            "store_type": "google_play",
            "star_rating": 1,
            "title": "Bad pricing",
            "body": "The delivery fee is too high and coupon swiggy50 failed to apply at checkout for my order.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        },
        {
            "store_type": "apple_app_store",
            "star_rating": 2,
            "title": "Late delivery",
            "body": "Delivery partner was delayed by 45 minutes and GPS tracking frozen on the map.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    ]
    input_file = tmp_path / "test_reviews.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(sample_data, f)

    config = PulsatorConfig(archive_dir=str(tmp_path / "archives"))

    # Force fallback generator by mocking httpx request to raise exception or return mock
    with patch("httpx.post", side_effect=Exception("Offline mock for test")):
        res = run_pipeline(
            input_path=str(input_file),
            config=config,
            dry_run=True,
            output_dir=str(tmp_path / "archives")
        )

    assert res["status"] == "SUCCESS_DRY_RUN"
    assert "word_count" in res
    assert os.path.exists(res["json_path"])
    assert os.path.exists(res["md_path"])
    assert os.path.exists(res["html_path"])


def test_cli_pipeline_with_mock_mcp(tmp_path):
    """Test E2E pipeline with mock MCP tool caller simulating Google Docs and Gmail integration."""
    sample_data = [
        {
            "store_type": "google_play",
            "star_rating": 1,
            "title": "Buggy app",
            "body": "The app crashes whenever I open Instamart cart to pay.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    ]
    input_file = tmp_path / "test_reviews.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(sample_data, f)

    config = PulsatorConfig(archive_dir=str(tmp_path / "archives"), target_email="exec@swiggy.in")

    def mock_mcp_caller(tool_name, args):
        if tool_name == "mcp_gdocs_create_doc":
            return {"doc_id": "mock_doc_123", "doc_url": "https://docs.google.com/document/d/mock_doc_123/edit"}
        if tool_name == "mcp_gmail_create_draft":
            return {"draft_id": "mock_draft_456"}
        return {}

    with patch("httpx.post", side_effect=Exception("Offline mock for test")):
        res = run_pipeline(
            input_path=str(input_file),
            config=config,
            dry_run=False,
            mcp_tool_caller=mock_mcp_caller
        )

    assert res["status"] == "SUCCESS"
    delivery = res["delivery"]
    assert delivery["gdocs_status"] == "SUCCESS"
    assert delivery["gmail_status"] == "SUCCESS"
    assert delivery["doc_id"] == "mock_doc_123"
    assert delivery["draft_id"] == "mock_draft_456"
