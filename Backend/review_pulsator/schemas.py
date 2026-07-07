"""
Core Pydantic schemas defining data contracts for Review Pulsator.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class RawReview(BaseModel):
    """
    Represents raw review data ingested from mobile store exports.
    """
    review_id: str = Field(..., min_length=1, description="Unique identifier for the review")
    store: str = Field(..., description="Store source, e.g., GOOGLE_PLAY or APPLE_APP_STORE")
    user_name: str = Field(default="Anonymous", description="Author or username of the reviewer")
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 to 5")
    title: str = Field(default="", description="Title of the review")
    body: str = Field(..., min_length=1, description="Body text of the review")
    submitted_at: datetime = Field(..., description="Timestamp of review submission")

    @field_validator("store")
    @classmethod
    def validate_store(cls, value: str) -> str:
        valid_stores = {"GOOGLE_PLAY", "APPLE_APP_STORE"}
        val_upper = value.upper()
        if val_upper not in valid_stores:
            raise ValueError(f"Invalid store: {value}. Must be one of {valid_stores}")
        return val_upper


class SanitizedReview(BaseModel):
    """
    Represents a review that has passed through preprocessing and PII scrubbing.
    """
    review_id: str
    store: str
    user_name: str = Field(default="Anonymous", description="Author or username of the reviewer")
    rating: int = Field(..., ge=1, le=5)
    title: str
    body: str
    submitted_at: datetime
    is_pii_scrubbed: bool = Field(default=True, description="Flag indicating PII scrubbing completion")
    imputed_timestamp: bool = Field(default=False, description="Flag indicating if timestamp was imputed")


class ThemeCluster(BaseModel):
    """
    Represents a cluster of reviews categorized under a domain theme.
    """
    theme_id: str
    theme_name: str
    review_count: int = Field(..., ge=0)
    average_rating: float = Field(..., ge=1.0, le=5.0)
    rank: int = Field(..., ge=1)
    representative_quotes: List[str] = Field(default_factory=list)
    sentiment_severity_score: float = Field(default=0.0, ge=0.0)


class ThemeSummary(BaseModel):
    """
    Summary of a top theme for presentation in the pulse report.
    """
    name: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)


class WeeklyPulseReport(BaseModel):
    """
    Final JSON payload representing the one-page weekly note (<=250 words)
    to be delivered via MCP to Google Docs and Gmail.
    """
    report_date: str = Field(..., description="Date of the report in YYYY-MM-DD format")
    word_count: int = Field(..., ge=0, le=250, description="Total word count of the note, must be <= 250")
    top_themes: List[ThemeSummary] = Field(..., max_length=3, description="Up to 3 highlighted top themes")
    verbatim_quotes: List[str] = Field(..., max_length=3, description="Up to 3 verbatim anonymous user quotes")
    action_ideas: List[str] = Field(..., max_length=3, description="Up to 3 concrete action ideas")

    @model_validator(mode="after")
    def check_word_count(self) -> "WeeklyPulseReport":
        if self.word_count > 250:
            raise ValueError(f"word_count ({self.word_count}) exceeds the strict ceiling of 250 words.")
        return self
