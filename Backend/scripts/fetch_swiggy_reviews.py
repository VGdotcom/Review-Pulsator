"""
Script to fetch public mobile store reviews for Swiggy (Food Delivery & Instamart)
and generate an 8-12 week export dataset for the Review Pulsator pipeline.
"""
import os
import json
import csv
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from google_play_scraper import Sort, reviews


def fetch_google_play_reviews(app_id: str = "in.swiggy.android", count: int = 500, max_weeks: int = 12):
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


def fetch_apple_rss_reviews(app_id: str = "989540920", country: str = "in", max_pages: int = 3):
    """
    Attempt to fetch real public customer reviews from Apple iTunes RSS feed.
    """
    reviews = []
    print(f"Attempting to fetch live Apple App Store reviews for ID {app_id}...")
    ctx = ssl._create_unverified_context()
    for page in range(1, max_pages + 1):
        url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                entries = data.get("feed", {}).get("entry", [])
                if isinstance(entries, dict):
                    entries = [entries]
                for idx, entry in enumerate(entries):
                    if idx == 0 and "im:name" in entry:
                        continue  # First entry is often app metadata
                    rev_id = entry.get("id", {}).get("label", f"apple_{page}_{idx}")
                    user_name = entry.get("author", {}).get("name", {}).get("label", "Anonymous")
                    rating = int(entry.get("im:rating", {}).get("label", 3))
                    title = entry.get("title", {}).get("label", "")
                    body = entry.get("content", {}).get("label", "")
                    submitted_at = entry.get("updated", {}).get("label", datetime.now(timezone.utc).isoformat())
                    reviews.append({
                        "review_id": str(rev_id),
                        "store": "APPLE_APP_STORE",
                        "user_name": str(user_name),
                        "rating": rating,
                        "title": title,
                        "body": body,
                        "submitted_at": submitted_at,
                    })
        except Exception as e:
            print(f"Note: Could not fetch page {page} from iTunes RSS ({str(e)}). Using grounded dataset.")
            break
    return reviews


def generate_swiggy_dataset():
    """
    Generate a comprehensive 8-12 week public review export dataset grounded in real
    Swiggy food delivery, Instamart grocery, and Swiggy One user experiences.
    Includes realistic PII injection for audit validation.
    """
    now = datetime.now(timezone.utc)
    
    sample_reviews = [
        # Theme 1: Delivery Speed & Partner Behavior
        {
            "review_id": "swg_play_001",
            "store": "GOOGLE_PLAY",
            "rating": 1,
            "title": "Cold food and 50 mins late",
            "body": "My order arrived almost an hour late during dinner rush. Delivery executive GPS tracking was stuck in one location for 30 minutes. Contact me at rahul.sharma@gmail.com for order ID 849201.",
            "weeks_ago": 2,
        },
        {
            "review_id": "swg_app_002",
            "store": "APPLE_APP_STORE",
            "rating": 2,
            "title": "Delivery partner behavior",
            "body": "The delivery partner refused to come up in the elevator and left the food at the security gate. Very rude behavior.",
            "weeks_ago": 4,
        },
        {
            "review_id": "swg_play_003",
            "store": "GOOGLE_PLAY",
            "rating": 5,
            "title": "Super fast delivery",
            "body": "Ordered biryani and got it hot within 25 minutes! Swiggy genie is also very helpful for sending packages.",
            "weeks_ago": 3,
        },
        
        # Theme 2: Order Accuracy & Packaging
        {
            "review_id": "swg_app_004",
            "store": "APPLE_APP_STORE",
            "rating": 1,
            "title": "Missing items in order",
            "body": "Ordered 4 burgers from Burger King but only received 3. The packaging was crushed and drink was spilled inside the bag.",
            "weeks_ago": 5,
        },
        {
            "review_id": "swg_play_005",
            "store": "GOOGLE_PLAY",
            "rating": 2,
            "title": "Wrong item delivered",
            "body": "Received veg noodles instead of chicken noodles. Automated customer care chat bot closed my complaint without refunding. My number is +91 98765-43210.",
            "weeks_ago": 6,
        },

        # Theme 3: Instamart & Grocery Experience
        {
            "review_id": "swg_play_006",
            "store": "GOOGLE_PLAY",
            "rating": 1,
            "title": "Instamart items out of stock without notice",
            "body": "Half of my Instamart grocery items were marked out of stock after placing the order and I was charged full amount. No replacement call was made.",
            "weeks_ago": 7,
        },
        {
            "review_id": "swg_app_007",
            "store": "APPLE_APP_STORE",
            "rating": 5,
            "title": "Instamart is a lifesaver",
            "body": "Got milk, bread and snacks delivered in literally 10 minutes at 11 PM. Great grocery selection and fast billing.",
            "weeks_ago": 3,
        },
        {
            "review_id": "swg_play_008",
            "store": "GOOGLE_PLAY",
            "rating": 2,
            "title": "Vegetables freshness issue on Instamart",
            "body": "The tomatoes and spinach ordered via Instamart were stale. Please improve quality checks at dark stores.",
            "weeks_ago": 8,
        },

        # Theme 4: Pricing, Coupons & Swiggy One
        {
            "review_id": "swg_app_009",
            "store": "APPLE_APP_STORE",
            "rating": 1,
            "title": "Swiggy One free delivery coupon not applying",
            "body": "I paid Rs 1499 for annual Swiggy One membership but at checkout it still adds Rs 45 delivery fee! The coupon says not applicable on restaurant.",
            "weeks_ago": 5,
        },
        {
            "review_id": "swg_play_010",
            "store": "GOOGLE_PLAY",
            "rating": 2,
            "title": "Surge fee is too high",
            "body": "During slight rain they charge Rs 60 extra rain surge plus packaging charge plus platform fee. Swiggy has become too expensive compared to Zomato.",
            "weeks_ago": 9,
        },

        # Theme 5: App Performance & Payment Glitches
        {
            "review_id": "swg_app_011",
            "store": "APPLE_APP_STORE",
            "rating": 1,
            "title": "GPS live tracking freeze on iPhone",
            "body": "The live map tracking freezes completely on iOS 17.4. I have to force close and reopen the app every 5 minutes to see where my order is.",
            "weeks_ago": 4,
        },
        {
            "review_id": "swg_play_012",
            "store": "GOOGLE_PLAY",
            "rating": 2,
            "title": "UPI payment money deducted but order failed",
            "body": "Paid via Google Pay UPI, amount debited from my HDFC bank account but Swiggy app showed payment failed. Device UUID 550e8400-e29b-41d4-a716-446655440000.",
            "weeks_ago": 6,
        },
        {
            "review_id": "swg_play_013",
            "store": "GOOGLE_PLAY",
            "rating": 5,
            "title": "Smooth UI and Dineout discounts",
            "body": "The app interface is super clean and paying restaurant bills via Swiggy Dineout gives great flat 25% discount on HDFC credit card.",
            "weeks_ago": 2,
        },
        
        # Old review (outside 12 week window - should be filtered by ingestion)
        {
            "review_id": "swg_old_014",
            "store": "GOOGLE_PLAY",
            "rating": 1,
            "title": "Old crash issue",
            "body": "App crashed when opening coupons page.",
            "weeks_ago": 15,
        },
        # Spam review (< 3 alnum chars - should be filtered by ingestion)
        {
            "review_id": "swg_spam_015",
            "store": "APPLE_APP_STORE",
            "rating": 5,
            "title": "Nice",
            "body": "!!",
            "weeks_ago": 3,
        }
    ]

    dataset = []
    for item in sample_reviews:
        sub_dt = now - timedelta(weeks=item["weeks_ago"])
        dataset.append({
            "review_id": item["review_id"],
            "store": item["store"],
            "user_name": item.get("user_name", "Anonymous"),
            "rating": item["rating"],
            "title": item["title"],
            "body": item["body"],
            "submitted_at": sub_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return dataset


def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("archives", exist_ok=True)
    
    # Fetch live Google Play Store reviews
    live_play = fetch_google_play_reviews("in.swiggy.android", count=500, max_weeks=12)
    
    # Try fetching live RSS reviews from Apple App Store
    live_apple = fetch_apple_rss_reviews("989540920")
    
    # Combine with realistic grounded dataset covering all 5 themes and edge cases
    grounded_reviews = generate_swiggy_dataset()
    all_reviews = live_play + live_apple + grounded_reviews
    
    # Save as JSON export
    json_path = os.path.join("data", "swiggy_reviews.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, indent=2)
    print(f"Successfully generated JSON review export: {json_path} ({len(all_reviews)} records)")

    # Save as CSV export
    csv_path = os.path.join("data", "swiggy_reviews.csv")
    if all_reviews:
        keys = ["review_id", "store", "user_name", "rating", "title", "body", "submitted_at"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in all_reviews:
                writer.writerow({k: row.get(k, "") for k in keys})
        print(f"Successfully generated CSV review export: {csv_path}")


if __name__ == "__main__":
    main()
