"""
Unit tests verifying Phase 1 configuration loading and JSON logging.
"""
import os
import json
import logging
from unittest.mock import patch
from review_pulsator.config import PulsatorConfig, setup_logging, get_logger, JSONFormatter


def test_default_config():
    config = PulsatorConfig()
    assert config.time_window_min_weeks == 8
    assert config.time_window_max_weeks == 12
    assert config.max_themes == 5
    assert config.top_themes_count == 3
    assert config.word_count_ceiling == 250
    assert config.log_level == "INFO"
    assert config.groq_model == "llama-3.3-70b-versatile"
    assert config.groq_temperature == 0.4
    assert config.groq_max_rpm == 30
    assert config.groq_max_rpd == 1000
    assert config.groq_max_tpm == 12000
    assert config.groq_max_tpd == 100000
    assert config.target_email == "user@example.com"
    assert config.gdocs_doc_id is None


def test_config_from_env():
    env_vars = {
        "PULSATOR_TIME_WINDOW_MIN_WEEKS": "6",
        "PULSATOR_TIME_WINDOW_MAX_WEEKS": "10",
        "PULSATOR_MAX_THEMES": "4",
        "PULSATOR_TOP_THEMES_COUNT": "2",
        "PULSATOR_WORD_COUNT_CEILING": "200",
        "PULSATOR_LOG_LEVEL": "DEBUG",
        "GROQ_MODEL": "llama-3.3-70b-custom",
        "GROQ_TEMPERATURE": "0.7",
        "GROQ_MAX_RPM": "15",
        "GROQ_MAX_RPD": "500",
        "GROQ_MAX_TPM": "6000",
        "GROQ_MAX_TPD": "50000",
        "PULSATOR_TARGET_EMAIL": "team@swiggy.in",
        "PULSATOR_GDOCS_DOC_ID": "doc_12345",
    }
    with patch.dict(os.environ, env_vars):
        config = PulsatorConfig.from_env()
        assert config.time_window_min_weeks == 6
        assert config.time_window_max_weeks == 10
        assert config.max_themes == 4
        assert config.top_themes_count == 2
        assert config.word_count_ceiling == 200
        assert config.log_level == "DEBUG"
        assert config.groq_model == "llama-3.3-70b-custom"
        assert config.groq_temperature == 0.7
        assert config.groq_max_rpm == 15
        assert config.groq_max_rpd == 500
        assert config.groq_max_tpm == 6000
        assert config.groq_max_tpd == 50000
        assert config.target_email == "team@swiggy.in"
        assert config.gdocs_doc_id == "doc_12345"


def test_json_formatter():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    formatted_str = formatter.format(record)
    log_obj = json.loads(formatted_str)
    assert log_obj["level"] == "INFO"
    assert log_obj["logger"] == "test_logger"
    assert log_obj["message"] == "Test message"
    assert "timestamp" in log_obj


def test_setup_logging():
    config = PulsatorConfig(log_level="DEBUG")
    setup_logging(config)
    logger = get_logger("test_service")
    assert logger.name == "review_pulsator.test_service"
