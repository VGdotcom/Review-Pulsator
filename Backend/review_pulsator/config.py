"""
Central configuration management and structured JSON logging for Review Pulsator.
"""
import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class PulsatorConfig(BaseModel):
    """
    Central configuration settings for the Review Pulsator pipeline.
    """
    time_window_min_weeks: int = Field(default=8, ge=1, description="Minimum weeks of review data to retain")
    time_window_max_weeks: int = Field(default=12, ge=1, description="Maximum weeks of review data to retain")
    max_themes: int = Field(default=5, ge=1, le=10, description="Maximum number of themes for clustering")
    top_themes_count: int = Field(default=3, ge=1, le=5, description="Number of top themes to highlight in report")
    word_count_ceiling: int = Field(default=250, ge=50, le=500, description="Strict word count ceiling for weekly note")
    log_level: str = Field(default="INFO", description="Logging verbosity level")
    archive_dir: str = Field(default="archives", description="Directory path for offline fallback archives")
    
    # --- Groq LLM & Rate Limit Constraints ---
    groq_model: str = Field(default="llama-3.3-70b-versatile", description="Groq model name")
    groq_temperature: float = Field(default=0.4, ge=0.0, le=2.0, description="Groq LLM sampling temperature")
    groq_max_rpm: int = Field(default=30, ge=1, description="Groq rate limit: Requests per minute")
    groq_max_rpd: int = Field(default=1000, ge=1, description="Groq rate limit: Requests per day")
    groq_max_tpm: int = Field(default=12000, ge=100, description="Groq rate limit: Tokens per minute")
    groq_max_tpd: int = Field(default=100000, ge=1000, description="Groq rate limit: Tokens per day")
    
    # --- MCP Delivery Constraints (Phase 5) ---
    target_email: str = Field(default="user@example.com", description="Target email for Gmail draft")
    gdocs_doc_id: Optional[str] = Field(default=None, description="Existing Google Doc ID to update")

    @classmethod
    def from_env(cls) -> "PulsatorConfig":
        """
        Load configuration from environment variables with safe fallback defaults.
        """
        return cls(
            time_window_min_weeks=int(os.getenv("PULSATOR_TIME_WINDOW_MIN_WEEKS", 8)),
            time_window_max_weeks=int(os.getenv("PULSATOR_TIME_WINDOW_MAX_WEEKS", 12)),
            max_themes=int(os.getenv("PULSATOR_MAX_THEMES", 5)),
            top_themes_count=int(os.getenv("PULSATOR_TOP_THEMES_COUNT", 3)),
            word_count_ceiling=int(os.getenv("PULSATOR_WORD_COUNT_CEILING", 250)),
            log_level=os.getenv("PULSATOR_LOG_LEVEL", "INFO").upper(),
            archive_dir=os.getenv("PULSATOR_ARCHIVE_DIR", "archives"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            groq_temperature=float(os.getenv("GROQ_TEMPERATURE", 0.4)),
            groq_max_rpm=int(os.getenv("GROQ_MAX_RPM", 30)),
            groq_max_rpd=int(os.getenv("GROQ_MAX_RPD", 1000)),
            groq_max_tpm=int(os.getenv("GROQ_MAX_TPM", 12000)),
            groq_max_tpd=int(os.getenv("GROQ_MAX_TPD", 100000)),
            target_email=os.getenv("PULSATOR_TARGET_EMAIL", "user@example.com"),
            gdocs_doc_id=os.getenv("PULSATOR_GDOCS_DOC_ID") or None,
        )


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs log records as structured JSON strings.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_obj.update(record.extra_data)
        return json.dumps(log_obj)


def setup_logging(config: PulsatorConfig) -> None:
    """
    Configure the root logger with JSON formatting.
    """
    logger = logging.getLogger("review_pulsator")
    logger.setLevel(getattr(logging, config.log_level, logging.INFO))
    
    # Remove existing handlers to prevent duplicate logging
    if logger.hasHandlers():
        logger.handlers.clear()
        
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Retrieve a logger instance scoped under review_pulsator.
    """
    return logging.getLogger(f"review_pulsator.{name}")
