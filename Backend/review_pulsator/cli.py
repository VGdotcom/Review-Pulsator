"""
Command Line Interface (CLI) & Pipeline Orchestrator for Review Pulsator (Phase 6).
Connects all pipeline stages:
  Ingestion -> PII Scrubbing -> Clustering -> Synthesis -> MCP Delivery
"""
import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from review_pulsator.config import PulsatorConfig
from review_pulsator.ingestion import IngestionService
from review_pulsator.clustering import ThemingEngine
from review_pulsator.synthesis import PulseGenerator
from review_pulsator.delivery import MCPIntegrationService
from review_pulsator.schemas import WeeklyPulseReport

logger = logging.getLogger("review_pulsator.cli")


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the pipeline."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stdout
    )


def run_pipeline(
    input_path: str,
    config: Optional[PulsatorConfig] = None,
    dry_run: bool = False,
    target_email: Optional[str] = None,
    doc_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    mcp_tool_caller: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Execute the full end-to-end Review Pulsator pipeline.
    
    :param input_path: Path to raw reviews JSON or CSV export.
    :param config: Optional PulsatorConfig override.
    :param dry_run: If True, skips MCP delivery and saves locally.
    :param target_email: Override target email for Gmail draft.
    :param doc_id: Override Google Docs doc ID for update.
    :param output_dir: Directory to save archive outputs.
    :param mcp_tool_caller: Callable function for MCP tool execution.
    :return: Summary dictionary containing execution status and artifacts.
    """
    config = config or PulsatorConfig.from_env()
    if output_dir:
        config.archive_dir = output_dir
    os.makedirs(config.archive_dir, exist_ok=True)

    logger.info(f"Starting Review Pulsator E2E Pipeline | Input: '{input_path}' | Dry Run: {dry_run}")
    print("=" * 70)
    print("🚀 REVIEW PULSATOR — END-TO-END PIPELINE ORCHESTRATOR")
    print("=" * 70)
    print(f"[Config] Model: {config.groq_model} (Temp: {config.groq_temperature})")
    print(f"[Config] Word Ceiling: {config.word_count_ceiling} | Max Themes: {config.max_themes}")
    print(f"[Input]  Source file: {input_path}")
    print("-" * 70)

    # --- Step 1: Ingestion & PII Scrubbing ---
    print("\n[Stage 1/4] 📥 Ingestion & PII Scrubbing (Regex + NER)...")
    ingestion = IngestionService()
    if not os.path.exists(input_path):
        err = f"Input file not found: {input_path}"
        logger.error(err)
        raise FileNotFoundError(err)

    sanitized_reviews = ingestion.load_reviews_from_file(input_path)
    print(f"✅ Extracted and scrubbed {len(sanitized_reviews)} valid English reviews (8-12 week window).")
    if not sanitized_reviews:
        raise ValueError("No valid reviews remained after time-window and language filtering.")

    # --- Step 2: Theming & Clustering ---
    print("\n[Stage 2/4] 🧩 Bounded Clustering & Sentiment Taxonomy Ranking...")
    theming = ThemingEngine(config=config)
    clusters = theming.cluster_reviews(sanitized_reviews)
    print(f"✅ Formed {len(clusters)} domain theme clusters. Top 3 drivers:")
    for idx, c in enumerate(clusters[:3], 1):
        print(f"   [{idx}] {c.theme_name} | Vol: {c.review_count} | Score: {c.sentiment_severity_score:.2f} | {c.average_rating}⭐")

    # --- Step 3: Synthesis ---
    print(f"\n[Stage 3/4] 🤖 Executive Pulse Synthesis via Groq ({config.groq_model})...")
    generator = PulseGenerator(config=config)
    report = generator.generate_pulse(clusters)
    print(f"✅ Generated executive summary: {report.word_count} / {config.word_count_ceiling} words.")
    print("-" * 70)
    print(f"📌 Top 1: {report.top_themes[0].name} ({report.top_themes[0].summary})")
    print(f"💬 Quote: \"{report.verbatim_quotes[0]}\"")
    print("-" * 70)

    # --- Step 4: Delivery & Archiving ---
    print("\n[Stage 4/4] 📤 Workspace Delivery (Google Docs & Gmail MCP)...")
    delivery = MCPIntegrationService(config=config, mcp_tool_caller=mcp_tool_caller)

    if dry_run:
        print("🛑 DRY-RUN MODE ENABLED: Skipping remote MCP tool calls.")
        archive_dir = os.path.join(config.archive_dir, "dry_run_reports")
        os.makedirs(archive_dir, exist_ok=True)
        json_path = os.path.join(archive_dir, f"pulse_{report.report_date}.json")
        md_path = os.path.join(archive_dir, f"pulse_{report.report_date}.md")
        html_path = os.path.join(archive_dir, f"pulse_{report.report_date}.html")

        gdocs_md = delivery.format_for_gdocs(report)
        gmail_html = delivery.format_for_gmail(report, doc_url="[Dry Run Local File]")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(gdocs_md)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(gmail_html)

        print(f"✅ Saved Dry-Run JSON Report: {json_path}")
        print(f"✅ Saved Dry-Run Markdown Report: {md_path}")
        print(f"✅ Saved Dry-Run Gmail HTML Draft: {html_path}")
        print("=" * 70)
        return {
            "status": "SUCCESS_DRY_RUN",
            "report_date": report.report_date,
            "word_count": report.word_count,
            "json_path": json_path,
            "md_path": md_path,
            "html_path": html_path,
        }

    # Execute MCP Delivery
    delivery_res = delivery.deliver_report(report, target_email=target_email, doc_id=doc_id)
    print(f"✅ Delivery Status: {delivery_res['status']}")
    print(f"📄 Google Docs Status: {delivery_res['gdocs_status']} | URL: {delivery_res['doc_url']}")
    print(f"📧 Gmail Draft Status: {delivery_res['gmail_status']} | Draft ID: {delivery_res['draft_id']}")
    if delivery_res.get("archive_path"):
        print(f"📂 Offline/Backup Archive: {delivery_res['archive_path']}")
    print("=" * 70)

    return {
        "status": delivery_res["status"],
        "report_date": report.report_date,
        "word_count": report.word_count,
        "delivery": delivery_res,
    }


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Review Pulsator — End-to-End AI Feedback Summarization Pipeline")
    parser.add_argument(
        "--input",
        type=str,
        default="data/swiggy_reviews.json",
        help="Path to input review dataset CSV or JSON file (default: data/swiggy_reviews.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline locally and output markdown/HTML archives without invoking live MCP Workspace tools"
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Override target email address for Gmail draft notification"
    )
    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,
        help="Override target Google Doc ID to update existing document"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override archive directory path for generated report artifacts"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging verbosity level"
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    try:
        run_pipeline(
            input_path=args.input,
            dry_run=args.dry_run,
            target_email=args.email,
            doc_id=args.doc_id,
            output_dir=args.output_dir,
        )
        return 0
    except Exception as e:
        logger.exception(f"Fatal pipeline error: {e}")
        print(f"\n❌ FATAL PIPELINE ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
