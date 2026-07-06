"""
Standalone Google Play Store review downloader for Swiggy.
Extracts live customer reviews for app package 'in.swiggy.android' within the last 8-12 weeks.
"""
import sys
import json
from datetime import datetime, timezone, timedelta
from google_play_scraper import Sort, reviews


def download_play_store_reviews(max_weeks: int = 12, max_count: int = 500):
    print("=== GOOGLE PLAY STORE STANDALONE DOWNLOADER ===")
    print(f"Targeting Package ID: in.swiggy.android | Time Window: Last {max_weeks} weeks")
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(weeks=max_weeks)
    
    try:
        result, _ = reviews(
            "in.swiggy.android",
            lang="en",
            country="in",
            sort=Sort.NEWEST,
            count=max_count,
        )
    except Exception as e:
        print(f"Error connecting to Google Play API: {str(e)}")
        sys.exit(1)
        
    play_reviews = []
    for r in result:
        dt = r["at"]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        if dt < cutoff_date:
            continue
            
        content_str = str(r.get("content", "")).strip()
        title_str = content_str.split(".")[0][:40] if content_str else "Swiggy Review"
        
        play_reviews.append({
            "review_id": f"play_{r['reviewId']}",
            "store": "GOOGLE_PLAY",
            "user_name": str(r.get("userName", "Anonymous")).strip(),
            "rating": int(r["score"]),
            "title": title_str.strip(),
            "body": content_str,
            "submitted_at": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        
    print(f"Successfully extracted {len(play_reviews)} live reviews from Google Play Store!")
    
    output_path = "data/swiggy_playstore_only.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(play_reviews, f, indent=2, ensure_ascii=False)
        
    print(f"Saved raw Play Store reviews to: {output_path}")
    return play_reviews


if __name__ == "__main__":
    download_play_store_reviews()
