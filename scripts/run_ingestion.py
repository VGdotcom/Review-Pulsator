"""
CLI tool to run Phase 2 IngestionService on review export files,
apply PII scrubbing, and export the sanitized results for inspection.
"""
import sys
import os
import json
import argparse
from review_pulsator.ingestion import IngestionService


def main():
    parser = argparse.ArgumentParser(description="Run Review Pulsator Phase 2 Ingestion & PII Scrubbing.")
    parser.add_argument("--input", "-i", default="data/swiggy_reviews.json", help="Path to input review file (.json or .csv)")
    parser.add_argument("--output", "-o", default="archives/extracted_swiggy_reviews.json", help="Path to save sanitized JSON output")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    print(f"Loading and sanitizing reviews from: {args.input}...")
    service = IngestionService()
    sanitized_reviews = service.load_reviews_from_file(args.input)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    
    # Dump to JSON
    output_data = [rev.model_dump(mode="json") for rev in sanitized_reviews]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n--- Ingestion & PII Scrubbing Complete ---")
    print(f"Total Valid Sanitized Reviews Extracted: {len(sanitized_reviews)}")
    print(f"Saved extracted data to: {args.output}\n")
    
    print("Preview of first 3 extracted & scrubbed reviews:")
    print("-" * 60)
    for idx, rev in enumerate(sanitized_reviews[:3], 1):
        print(f"[{idx}] ID: {rev.review_id} | Store: {rev.store} | User: {rev.user_name} | Rating: {rev.rating}⭐")
        print(f"    Title: {rev.title}")
        print(f"    Body:  {rev.body}")
        print("-" * 60)


if __name__ == "__main__":
    main()
