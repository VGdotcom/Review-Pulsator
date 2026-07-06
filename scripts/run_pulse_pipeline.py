"""
End-to-End Sample Runner for Review Pulsator (Phases 1 through 4).
Runs ingestion & PII scrubbing on real Swiggy review data, clusters them into themes,
and calls the live Groq API (llama-3.3-70b-versatile @ temp 0.4) to generate the weekly pulse report.
"""
import os
import sys
import json
from datetime import datetime, timezone
from review_pulsator.config import PulsatorConfig
from review_pulsator.ingestion import IngestionService
from review_pulsator.clustering import ThemingEngine
from review_pulsator.synthesis import PulseGenerator


def main():
    print("=" * 70)
    print("🚀 REVIEW PULSATOR — END-TO-END SAMPLE PIPELINE TEST (PHASES 1-4)")
    print("=" * 70)

    # 1. Load Config & Verify Environment
    config = PulsatorConfig.from_env()
    print(f"\n[Config] Model: {config.groq_model} | Temp: {config.groq_temperature}")
    print(f"[Config] Max Themes: {config.max_themes} | Top Themes: {config.top_themes_count} | Word Ceiling: {config.word_count_ceiling}")
    
    input_path = "data/swiggy_reviews.json"
    if not os.path.exists(input_path):
        print(f"Error: Could not find raw review file at {input_path}")
        sys.exit(1)

    # 2. Phase 2: Ingestion & PII Scrubbing
    print(f"\n[Phase 2] Ingesting, cleaning, and scrubbing PII from: {input_path}...")
    ingestion_service = IngestionService()
    sanitized_reviews = ingestion_service.load_reviews_from_file(input_path)
    print(f"✅ Extracted {len(sanitized_reviews)} clean, normalized English reviews.")

    if not sanitized_reviews:
        print("Error: No reviews remained after filtering!")
        sys.exit(1)

    # 3. Phase 3: Theming & Clustering
    print(f"\n[Phase 3] Running clustering & sentiment taxonomy scoring...")
    theming_engine = ThemingEngine(config=config)
    clusters = theming_engine.cluster_reviews(sanitized_reviews)
    print(f"✅ Formed {len(clusters)} emerging theme clusters.")
    for idx, c in enumerate(clusters[:3], 1):
        print(f"   [{idx}] {c.theme_name} (ID: {c.theme_id}) | Reviews: {c.review_count} | Severity Score: {c.sentiment_severity_score:.2f} | Avg Rating: {c.average_rating}⭐")

    # 4. Phase 4: Pulse Synthesis (Groq LLM)
    print(f"\n[Phase 4] Synthesizing executive weekly pulse note using Groq API ({config.groq_model})...")
    generator = PulseGenerator(config=config)
    pulse_report = generator.generate_pulse(clusters)

    print("\n✅ WEEKLY PULSATOR EXECUTIVE REPORT GENERATED SUCCESSFULLY!")
    print("=" * 70)

    # Display Report in clean Markdown
    print(f"📅 REPORT DATE: {pulse_report.report_date}  |  📝 WORD COUNT: {pulse_report.word_count} / {config.word_count_ceiling} words")
    print("-" * 70)
    print("📌 TOP EMERGING THEMES:")
    for idx, t in enumerate(pulse_report.top_themes, 1):
        print(f"  {idx}. {t.name}\n     {t.summary}")
    
    print("\n💬 VERBATIM ANONYMOUS QUOTES:")
    for idx, q in enumerate(pulse_report.verbatim_quotes, 1):
        print(f'  {idx}. "{q}"')
        
    print("\n🎯 RECOMMENDED ACTION IDEAS:")
    for idx, a in enumerate(pulse_report.action_ideas, 1):
        print(f"  {idx}. {a}")
    print("=" * 70)

    # 5. Save output artifacts
    os.makedirs(config.archive_dir, exist_ok=True)
    json_out_path = os.path.join(config.archive_dir, "sample_swiggy_weekly_pulse.json")
    with open(json_out_path, "w", encoding="utf-8") as f:
        json.dump(pulse_report.model_dump(), f, indent=2)

    md_out_path = os.path.join(config.archive_dir, "sample_swiggy_weekly_pulse.md")
    with open(md_out_path, "w", encoding="utf-8") as f:
        f.write(f"# 🛵 Swiggy Weekly Pulse Report ({pulse_report.report_date})\n\n")
        f.write(f"**Total Word Count:** {pulse_report.word_count} / {config.word_count_ceiling} words\n\n")
        f.write("## 📌 Top Emerging Sentiment Themes\n")
        for idx, t in enumerate(pulse_report.top_themes, 1):
            f.write(f"### {idx}. {t.name}\n{t.summary}\n\n")
        f.write("## 💬 Verbatim Customer Quotes\n")
        for q in pulse_report.verbatim_quotes:
            f.write(f"> \"{q}\"\n\n")
        f.write("## 🎯 Recommended Action Ideas\n")
        for idx, a in enumerate(pulse_report.action_ideas, 1):
            f.write(f"{idx}. {a}\n")

    print(f"\n📂 Saved JSON report to: {json_out_path}")
    print(f"📂 Saved Markdown report to: {md_out_path}\n")


if __name__ == "__main__":
    main()
