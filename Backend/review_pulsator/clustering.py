"""
Clustering and Theming Engine for Review Pulsator (Phase 3).
Groups sanitized reviews into bounded domain taxonomies (<=5 themes)
and ranks them by volume and sentiment severity to extract Top 3 sentiment drivers.
"""
import re
import math
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from review_pulsator.config import PulsatorConfig
from review_pulsator.schemas import SanitizedReview, ThemeCluster


class ThemingEngine:
    """
    Engine responsible for grouping SanitizedReview items into Swiggy domain taxonomies,
    computing sentiment severity scores, and extracting top sentiment driver themes.
    """

    # 5 Bounded Domain Taxonomies for Swiggy
    TAXONOMIES = {
        "theme_delivery": {
            "name": "Delivery Speed & Partner Behavior",
            "keywords": [
                "late", "delay", "delayed", "time", "hour", "min", "minutes", "partner",
                "executive", "rider", "delivery", "rude", "tracking", "gps", "genie",
                "boy", "arrived", "cold", "waiting", "behaviour", "behavior", "status",
                "location", "map", "driver", "fast", "speed", "quick", "delivery boy"
            ]
        },
        "theme_accuracy": {
            "name": "Order Accuracy & Packaging",
            "keywords": [
                "wrong", "missing", "item", "items", "packaging", "spill", "spilled",
                "crushed", "leak", "leaked", "half", "portion", "received", "instead",
                "bad food", "stale", "quality", "taste", "hygiene", "rotten", "bug",
                "insect", "order", "food", "quantity", "cold food", "hot"
            ]
        },
        "theme_instamart": {
            "name": "Instamart & Grocery Experience",
            "keywords": [
                "instamart", "grocery", "groceries", "stock", "veggies", "fruit",
                "fruits", "milk", "vegetable", "vegetables", "bread", "egg", "eggs",
                "daily", "expired", "bag", "fresh", "supermarket", "store", "out of stock"
            ]
        },
        "theme_pricing": {
            "name": "Pricing, Refund & Customer Support",
            "keywords": [
                "price", "expensive", "coupon", "discount", "one", "membership", "swiggy one",
                "refund", "support", "charge", "fee", "handling", "money", "cheat", "cheating",
                "fraud", "care", "chat", "bot", "customer", "call", "contact", "response",
                "resolved", "issue", "help", "complain", "complaint", "waste", "service",
                "scam", "poor service", "pathetic", "worst", "bad service"
            ]
        },
        "theme_app": {
            "name": "App Performance & Usability",
            "keywords": [
                "app", "crash", "crashes", "crashing", "hang", "hangs", "freeze",
                "freezes", "bug", "bugs", "login", "update", "slow", "ui", "error",
                "glitch", "screen", "load", "loading", "payment", "pay", "upi", "interface",
                "work", "working", "install", "open", "opening"
            ]
        }
    }

    # Stopwords and generic praise words for noise detection
    STOPWORDS = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
        "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
        "by", "can", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
        "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
        "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
        "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
        "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she",
        "should", "so", "some", "such", "t", "than", "that", "the", "their", "theirs", "them",
        "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
        "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
        "while", "who", "whom", "why", "will", "with", "you", "your", "yours", "yourself", "yourselves"
    }

    GENERIC_NOISE_TERMS = {
        "good", "nice", "ok", "okay", "bad", "awesome", "super", "best", "love", "great",
        "worst", "poor", "excellent", "fine", "wow", "osm", "op", "nice app", "good app",
        "very good", "superb", "loved it", "best app", "good service", "bad app", "worst app"
    }

    def __init__(self, config: PulsatorConfig = None):
        self.config = config or PulsatorConfig.from_env()

    def _tokenize(self, text: str) -> List[str]:
        """Convert text into clean lowercase tokens without punctuation."""
        return re.findall(r"\b[a-z0-9]+\b", text.lower())

    def _is_noise(self, review: SanitizedReview) -> bool:
        """
        Check if review is uninformative generic noise (Edge-case 3.3).
        Reviews with fewer than 4 informative tokens or matching generic praise are flagged.
        """
        body_clean = review.body.strip().lower()
        title_clean = review.title.strip().lower()
        
        # Exact match against generic noise expressions
        if body_clean in self.GENERIC_NOISE_TERMS or f"{title_clean} {body_clean}".strip() in self.GENERIC_NOISE_TERMS:
            return True

        tokens = self._tokenize(f"{review.title} {review.body}")
        informative_tokens = [t for t in tokens if t not in self.STOPWORDS and len(t) > 1]
        
        # If less than 2 informative tokens, classify as low-information noise
        if len(informative_tokens) < 2:
            return True
            
        return False

    def _categorize_review(self, review: SanitizedReview) -> str:
        """
        Map a review to the highest scoring Swiggy domain taxonomy.
        Returns the theme_id.
        """
        text = f"{review.title} {review.body}".lower()
        tokens = set(self._tokenize(text))
        
        best_theme = None
        best_score = -1.0
        
        for theme_id, data in self.TAXONOMIES.items():
            score = 0.0
            for kw in data["keywords"]:
                if kw in text:
                    # Give higher weight to multi-word phrases or exact keyword matches
                    score += 2.0 if " " in kw else 1.0
            if score > best_score:
                best_score = score
                best_theme = theme_id
                
        # If no keywords matched at all, assign based on rating heuristics
        if best_score == 0 or best_theme is None:
            if review.rating <= 2:
                # Most negative default complaints in food delivery relate to support/pricing or delivery
                best_theme = "theme_pricing" if "swiggy" in text else "theme_delivery"
            else:
                best_theme = "theme_app"
                
        return best_theme

    def _extract_representative_quotes(self, reviews: List[SanitizedReview], max_quotes: int = 3) -> List[str]:
        """
        Select up to max_quotes verbatim sentences from cluster reviews.
        Guarantees exact substring matching for downstream Phase 4 validation.
        """
        quotes = []
        # Prioritize lower rated reviews (pain points) and informative sentence lengths (20-150 chars)
        sorted_reviews = sorted(reviews, key=lambda r: (r.rating, -len(r.body)))
        
        seen_quotes = set()
        for rev in sorted_reviews:
            if len(quotes) >= max_quotes:
                break
                
            # Split body into sentences or use whole body if short
            sentences = [s.strip() for s in re.split(r'[.!?]+', rev.body) if s.strip()]
            if not sentences:
                sentences = [rev.body.strip()]
                
            for sent in sentences:
                # Must be informative length and not already added
                if 15 <= len(sent) <= 200 and sent.lower() not in seen_quotes:
                    # Verify it's an exact substring of the body
                    if sent in rev.body:
                        quotes.append(sent)
                        seen_quotes.add(sent.lower())
                        break
            if len(quotes) >= max_quotes:
                break
                
        # If still need quotes, fallback to whole bodies of top reviews
        if not quotes and reviews:
            for rev in sorted_reviews[:max_quotes]:
                body_str = rev.body.strip()
                if body_str and body_str.lower() not in seen_quotes:
                    quotes.append(body_str)
                    seen_quotes.add(body_str.lower())
                    
        return quotes

    def cluster_reviews(self, reviews: List[SanitizedReview]) -> List[ThemeCluster]:
        """
        Group reviews into bounded domain taxonomies (<= max_themes), compute severity scores,
        and return sorted ThemeCluster objects.
        """
        if not reviews:
            # Edge-case 1.1: Zero reviews in time window
            return [ThemeCluster(
                theme_id="theme_empty",
                theme_name="No Volume",
                review_count=0,
                average_rating=5.0,
                rank=1,
                representative_quotes=["No verbatim quotes available for this period."],
                sentiment_severity_score=0.0,
            )]

        theme_groups: Dict[str, List[SanitizedReview]] = defaultdict(list)
        noise_reviews: List[SanitizedReview] = []

        for rev in reviews:
            if self._is_noise(rev):
                noise_reviews.append(rev)
            else:
                theme_id = self._categorize_review(rev)
                theme_groups[theme_id].append(rev)

        # If all reviews were classified as noise, put them in app usability or default
        if not theme_groups and noise_reviews:
            theme_groups["theme_app"] = noise_reviews

        clusters = []
        for theme_id, rev_list in theme_groups.items():
            count = len(rev_list)
            avg_rating = round(sum(r.rating for r in rev_list) / count, 2)
            
            # Ranking formula: Volume * SentimentSeverityWeight
            # Lower ratings get exponentially higher severity weight
            severity_weight = max(0.1, (5.0 - avg_rating) * 10.0 + 1.0)
            score = round(count * severity_weight, 2)
            
            quotes = self._extract_representative_quotes(rev_list, max_quotes=3)
            theme_name = self.TAXONOMIES.get(theme_id, {}).get("name", "General Feedback")

            clusters.append(ThemeCluster(
                theme_id=theme_id,
                theme_name=theme_name,
                review_count=count,
                average_rating=avg_rating,
                rank=1,  # Temporary placeholder before sorting
                representative_quotes=quotes,
                sentiment_severity_score=score,
            ))

        # Edge-case 3.2: Sort by composite score desc, then lower rating, then volume, then alphabetical id
        clusters.sort(key=lambda c: (-c.sentiment_severity_score, c.average_rating, -c.review_count, c.theme_id))

        # Bounding: limit to max_themes from config (default 5)
        max_themes = getattr(self.config, "max_themes", 5)
        bounded_clusters = clusters[:max_themes]

        # Assign deterministic rank
        for idx, clu in enumerate(bounded_clusters):
            clu.rank = idx + 1

        return bounded_clusters

    def get_top_themes(self, clusters: List[ThemeCluster], count: int = 3) -> List[ThemeCluster]:
        """
        Extract exactly the Top N scoring clusters for downstream synthesis.
        Handles Edge-case 3.1 (low cluster density) by appending safe placeholder themes if necessary.
        """
        top_clusters = clusters[:count]
        
        # Edge-case 3.1: If fewer than target count themes exist, pad with safe schema-compliant placeholders
        while len(top_clusters) < count and top_clusters:
            pad_idx = len(top_clusters) + 1
            top_clusters.append(ThemeCluster(
                theme_id=f"theme_pad_{pad_idx}",
                theme_name="[No Additional Distinct Themes Detected]",
                review_count=0,
                average_rating=5.0,
                rank=pad_idx,
                representative_quotes=["No additional distinct themes emerged during this cycle."],
                sentiment_severity_score=0.0,
            ))
            
        return top_clusters
