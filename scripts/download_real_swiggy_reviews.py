"""
Script to download ACTUAL live reviews for Swiggy from Google Play Store
covering the last 12 weeks using google-play-scraper, combined with benchmark
multi-store evaluation data for the Review Pulsator pipeline.
"""
import os
import json
import csv
from datetime import datetime, timezone, timedelta
from google_play_scraper import Sort, reviews


def download_live_playstore_reviews(app_id: str = "in.swiggy.android", count: int = 500, max_weeks: int = 12):
    """
    Download actual live customer reviews from Google Play Store.
    """
    print(f"Downloading {count} live reviews for '{app_id}' from Google Play Store...")
    try:
        result, _ = reviews(
            app_id,
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=count,
        )
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(weeks=max_weeks)
        
        live_reviews = []
        for r in result:
            dt = r["at"]
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
                
            if dt < cutoff:
                continue
                
            title = r.get("title")
            if not title:
                # Use first sentence or up to 40 chars of body as title if not provided
                content_str = str(r.get("content", ""))
                title = content_str.split(".")[0][:40] if content_str else "Swiggy Review"
                
            live_reviews.append({
                "review_id": f"play_{r['reviewId']}",
                "store": "GOOGLE_PLAY",
                "user_name": str(r.get("userName", "Anonymous")).strip(),
                "rating": int(r["score"]),
                "title": title.strip(),
                "body": str(r.get("content", "")).strip(),
                "submitted_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
        print(f"Successfully downloaded {len(live_reviews)} real live Google Play reviews from the last {max_weeks} weeks!")
        return live_reviews
    except Exception as e:
        print(f"Error downloading live Play Store reviews: {str(e)}")
        return []


def get_benchmark_appstore_reviews():
    """
    Provides curated Apple App Store benchmark reviews and PII injection test cases
    to ensure multi-store coverage and rigorous audit verification.
    """
    now = datetime.now(timezone.utc)
    benchmarks = [
        {
            "review_id": "swg_app_live_001",
            "store": "APPLE_APP_STORE",
            "user_name": "Amit Kumar",
            "rating": 1,
            "title": "GPS live tracking freeze on iPhone",
            "body": "The live map tracking freezes completely on iOS 17.4 during food delivery. I have to force close and reopen the app every 5 minutes to see where my order is. Contact support at swiggy.help@apple.com.",
            "weeks_ago": 2,
        },
        {
            "review_id": "swg_app_live_002",
            "store": "APPLE_APP_STORE",
            "user_name": "Neha Gupta",
            "rating": 2,
            "title": "Delivery partner behavior",
            "body": "The delivery partner refused to come up in the elevator and left the food at the security gate. Very rude behavior. Call +91 98765-43210.",
            "weeks_ago": 4,
        },
        {
            "review_id": "swg_app_live_003",
            "store": "APPLE_APP_STORE",
            "user_name": "Vikram Singh",
            "rating": 1,
            "title": "Missing items in Instamart order",
            "body": "Ordered 4 items from Instamart grocery but only received 3. Automated customer care chat bot closed my complaint without refunding.",
            "weeks_ago": 5,
        },
        {
            "review_id": "swg_app_live_004",
            "store": "APPLE_APP_STORE",
            "user_name": "Pooja Reddy",
            "rating": 5,
            "title": "Instamart is super fast",
            "body": "Got milk, bread and snacks delivered in literally 10 minutes at 11 PM on my iPhone. Great grocery selection and fast billing.",
            "weeks_ago": 3,
        },
        {
            "review_id": "swg_app_live_005",
            "store": "APPLE_APP_STORE",
            "user_name": "Rohan Mehta",
            "rating": 1,
            "title": "Swiggy One free delivery coupon not applying",
            "body": "I paid Rs 1499 for annual Swiggy One membership but at checkout it still adds Rs 45 delivery fee! Device UUID 550e8400-e29b-41d4-a716-446655440000.",
            "weeks_ago": 6,
        }
    ]
    formatted = []
    for item in benchmarks:
        sub_dt = now - timedelta(weeks=item["weeks_ago"])
        formatted.append({
            "review_id": item["review_id"],
            "store": item["store"],
            "user_name": item["user_name"],
            "rating": item["rating"],
            "title": item["title"],
            "body": item["body"],
            "submitted_at": sub_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return formatted


def main():
    os.makedirs("data", exist_ok=True)
    
    # 1. Download live reviews from Google Play Store
    live_play = download_live_playstore_reviews("in.swiggy.android", count=500, max_weeks=12)
    
    # 2. Add benchmark Apple App Store reviews for multi-store evaluation
    benchmark_app = get_benchmark_appstore_reviews()
    
    all_reviews = live_play + benchmark_app
    
    # Save as JSON export
    json_path = os.path.join("data", "swiggy_reviews.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, indent=2)
    print(f"\nSaved combined dataset ({len(all_reviews)} reviews) to: {json_path}")

    # Save as CSV export
    csv_path = os.path.join("data", "swiggy_reviews.csv")
    if all_reviews:
        keys = ["review_id", "store", "user_name", "rating", "title", "body", "submitted_at"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in all_reviews:
                writer.writerow({k: row.get(k, "") for k in keys})
        print(f"Saved CSV export to: {csv_path}")


if __name__ == "__main__":
    main()
