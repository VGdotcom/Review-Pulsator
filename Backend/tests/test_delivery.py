"""
Unit tests for Phase 5 MCP Delivery & Workspace Integration module.
"""
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from review_pulsator.config import PulsatorConfig
from review_pulsator.schemas import WeeklyPulseReport, ThemeSummary
from review_pulsator.delivery import MCPIntegrationService


@pytest.fixture
def sample_report():
    return WeeklyPulseReport(
        report_date="2026-07-06",
        word_count=150,
        top_themes=[
            ThemeSummary(name="Pricing & Refunds", summary="Customers complain about refund delays."),
            ThemeSummary(name="Delivery Speed", summary="Delivery is often late by 30 mins."),
            ThemeSummary(name="App Bugs", summary="App crashes during payment."),
        ],
        verbatim_quotes=[
            "Bad refund policy",
            "Late food delivery",
            "App crashes on checkout"
        ],
        action_ideas=[
            "Automate instant refund processing.",
            "Improve delivery routing and partner tracking.",
            "Fix checkout payment crash on iOS."
        ]
    )


def test_format_for_gdocs(sample_report):
    service = MCPIntegrationService()
    gdocs_text = service.format_for_gdocs(sample_report)
    assert "# 🛵 Swiggy Weekly Pulse Report (2026-07-06)" in gdocs_text
    assert "### 1. Pricing & Refunds" in gdocs_text
    assert '> "Bad refund policy"' in gdocs_text
    assert "1. Automate instant refund processing." in gdocs_text


def test_format_for_gmail(sample_report):
    service = MCPIntegrationService()
    gmail_html = service.format_for_gmail(sample_report, doc_url="https://docs.google.com/test_doc")
    assert "🛵 Swiggy Weekly Pulse Report (2026-07-06)" in gmail_html
    assert "https://docs.google.com/test_doc" in gmail_html
    assert "Automate instant refund processing." in gmail_html


def test_successful_mcp_delivery(sample_report, tmp_path):
    config = PulsatorConfig(archive_dir=str(tmp_path))
    
    # Mock MCP tool caller
    def mock_caller(tool_name, arguments):
        if tool_name == "mcp_gdocs_create_doc":
            return {"doc_id": "doc_999", "doc_url": "https://docs.google.com/document/d/doc_999"}
        if tool_name == "mcp_gmail_create_draft":
            return {"draft_id": "draft_888"}
        return {}

    service = MCPIntegrationService(config=config, mcp_tool_caller=mock_caller, retry_delays=[0])
    result = service.deliver_report(sample_report, target_email="test@swiggy.in")
    
    assert result["status"] == "SUCCESS"
    assert result["gdocs_status"] == "SUCCESS"
    assert result["gmail_status"] == "SUCCESS"
    assert result["doc_id"] == "doc_999"
    assert result["draft_id"] == "draft_888"


def test_degraded_offline_fallback(sample_report, tmp_path):
    config = PulsatorConfig(archive_dir=str(tmp_path))
    
    # Mock MCP caller that raises error (simulating offline server)
    def failing_caller(tool_name, arguments):
        raise RuntimeError("MCP Daemon Unreachable")

    service = MCPIntegrationService(config=config, mcp_tool_caller=failing_caller, retry_delays=[0, 0])
    result = service.deliver_report(sample_report)
    
    assert result["status"] == "DEGRADED"
    assert result["gdocs_status"] == "FAILED"
    assert result["gmail_status"] == "FAILED"
    assert result["archive_path"] is not None
    assert os.path.exists(result["archive_path"])
    
    with open(result["archive_path"], "r") as f:
        data = json.load(f)
        assert data["delivery_status"] == "DEGRADED_OFFLINE_ARCHIVE"
        assert "MCP Daemon Unreachable" in data["degradation_reason"]
