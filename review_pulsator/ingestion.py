"""
Ingestion service for reading, filtering, normalizing, and sanitizing public app store review exports.
Enforces data normalization rules:
1. Hindi reviews (Devanagari or Hinglish) are ignored.
2. Emojis and symbol pictographs are ignored/stripped.
3. Reviews with unclear meaning, gibberish, or uninformative noise are removed.
"""
import csv
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from review_pulsator.config import PulsatorConfig, get_logger
from review_pulsator.schemas import SanitizedReview
from review_pulsator.scrubber import PIIScrubber


class IngestionService:
    """
    Service responsible for loading public review exports (CSV/JSON),
    normalizing text (stripping emojis), filtering by language/meaning/time window,
    and applying PII scrubbing.
    """

    # Regex for detecting Devanagari Unicode script (Hindi)
    DEVANAGARI_PATTERN = re.compile(r"[\u0900-\u097F]")

    # Regex for stripping Emojis and symbol pictographs
    EMOJI_PATTERN = re.compile(
        r"["
        r"\U0001f600-\U0001f64f"  # emoticons
        r"\U0001f300-\U0001f5ff"  # symbols & pictographs
        r"\U0001f680-\U0001f6ff"  # transport & map symbols
        r"\U0001f1e0-\U0001f1ff"  # flags (iOS)
        r"\U00002702-\U000027b0"
        r"\U000024c2-\U0001f251"
        r"\U0001f900-\U0001f9ff"  # supplemental symbols
        r"\U0001fa70-\U0001faff"  # symbols and pictographs extended-a
        r"\u2600-\u26FF"          # miscellaneous symbols
        r"\u2700-\u27BF"          # dingbats
        r"\u200d\ufe0f"           # zero width joiners & variation selectors
        r"]+",
        flags=re.UNICODE,
    )

    # Hinglish / Romanized Hindi indicator words
    HINDI_STOPWORDS = {
        "bahut", "bhai", "hai", "kar", "nahi", "kya", "bekar", "bakwas", "ghatia",
        "acha", "mast", "fultoo", "paise", "khana", "kro", "kaise", "mera", "meri",
        "mene", "tum", "aap", "wala", "wali", "karna", "chahiye", "raha", "rahi",
        "hua", "gaya", "gayi", "sahi", "galat", "kuch", "koi", "bhi", "toh", "tha",
        "thi", "the", "mein", "par", "pe", "se", "ki", "ko", "ka", "ke", "diya",
        "laga", "bura", "dene", "mile", "milsa", "nhi", "kare", "karo", "rha", "rhi",
        "h", "k", "kr", "bhut", "accha", "bilkul", "mat", "kro", "karen", "de", "do"
    }

    # Uninformative generic noise / unclear meaning terms
    UNCLEAR_OR_NOISE_TERMS = {
        "good", "nice", "ok", "okay", "bad", "awesome", "super", "best", "love", "great",
        "worst", "poor", "excellent", "fine", "wow", "osm", "op", "nice app", "good app",
        "very good", "superb", "loved it", "best app", "good service", "bad app", "worst app",
        "hi", "hello", "test", "no", "yes", "hmm", "ahh", "nothing", "bakwas", "bekar",
        "very nice", "nice service", "good food", "nice food", "bad service", "worst service",
        "very bad", "pathetic", "thik", "theek", "thanks", "thank you", "swiggy", "app"
    }

    GENERIC_ADJECTIVES = {
        "good", "nice", "ok", "okay", "bad", "awesome", "super", "best", "love", "great",
        "worst", "poor", "excellent", "fine", "wow", "osm", "op", "superb", "loved", "tasty",
        "fast", "slow", "late", "pathetic", "thik", "theek", "thanks", "thank", "you", "very",
        "hard", "working", "helpful", "really", "much", "too", "so", "always", "ever", "never",
        "quick", "prompt", "amazing", "wonderful", "fabulous", "nicee", "goodd", "happy",
        "satisfied", "glad", "use", "useful", "useless", "cool", "easy"
    }

    GENERIC_NOUNS = {
        "app", "ap", "aps", "appp", "service", "food", "delivery", "experience", "boy", "boys",
        "guy", "guys", "agent", "agents", "person", "man", "staff", "team", "support", "swiggy",
        "order", "orders", "work", "job", "time", "quality", "partner", "partners", "executive",
        "one", "thing", "things", "people", "customer", "customers", "user", "users"
    }

    ENGLISH_STOPWORDS = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
        "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
        "by", "can", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
        "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
        "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more",
        "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
        "other", "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she", "should",
        "so", "some", "such", "t", "than", "that", "the", "their", "theirs", "them", "themselves",
        "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
        "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
        "why", "will", "with", "you", "your", "yours", "yourself", "yourselves"
    }

    def __init__(self, config: Optional[PulsatorConfig] = None, scrubber: Optional[PIIScrubber] = None):
        self.config = config or PulsatorConfig()
        self.scrubber = scrubber or PIIScrubber()
        self.logger = get_logger("ingestion")

    def _strip_emojis(self, text: str) -> str:
        """Rule 2: Strip emojis and symbol pictographs from text."""
        return self.EMOJI_PATTERN.sub("", text).strip()

    def _is_hindi(self, text: str) -> bool:
        """Rule 1: Check if text is in Hindi (Devanagari script or Hinglish)."""
        if not text:
            return False
        if self.DEVANAGARI_PATTERN.search(text):
            return True
            
        tokens = re.findall(r"\b[a-z]+\b", text.lower())
        if not tokens:
            return False
            
        hindi_count = sum(1 for t in tokens if t in self.HINDI_STOPWORDS)
        # If 2+ Hinglish tokens, or >25% of tokens are Hinglish words
        if hindi_count >= 2 or (hindi_count >= 1 and len(tokens) <= 3):
            return True
        return False

    def _is_unclear(self, title: str, body: str) -> bool:
        """Rule 3: Remove reviews with unclear meaning, gibberish, or generic noise."""
        body_clean = body.strip().lower()
        title_clean = title.strip().lower()
        full_text = f"{title_clean} {body_clean}".strip()

        # Check against generic uninformative terms
        if body_clean in self.UNCLEAR_OR_NOISE_TERMS or full_text in self.UNCLEAR_OR_NOISE_TERMS:
            return True

        # Check minimum alphanumeric length
        alnum_count = sum(1 for char in body if char.isalnum())
        if alnum_count < 3:
            return True

        tokens = re.findall(r"\b[a-z0-9]+\b", full_text)
        if not tokens:
            return True

        # Check for keyboard gibberish / single character repetition / keyboard rows (e.g. 'xxxx', 'asdfghjkl', 'qwerty')
        keyboard_rows = ("asdf", "qwer", "zxcv", "hjkl", "uiop", "nmjk")
        for t in tokens:
            if t.isalpha() and (any(row in t for row in keyboard_rows) or (len(t) > 3 and not any(v in t for v in "aeiouy"))):
                return True
        if all(len(set(t)) == 1 and len(t) > 2 for t in tokens):
            return True

        # Check informative token count after removing stopwords
        informative_tokens = [t for t in tokens if t not in self.ENGLISH_STOPWORDS and len(t) > 1]
        if len(informative_tokens) < 1:
            return True
            
        # If body is just 1 word without any additional context (e.g. 'osm', 'asdfghjkl', 'good', 'bad')
        body_tokens = re.findall(r"\b[a-z0-9]+\b", body_clean)
        if len(body_tokens) <= 1:
            return True

        # Check if distinct words in review are composed entirely of generic adjectives, nouns, and stopwords (e.g. 'good service', 'very hard working delivery boys', 'good one', 'happy with service')
        if len(set(tokens)) <= 6 and all(t in self.GENERIC_ADJECTIVES or t in self.GENERIC_NOUNS or t in self.ENGLISH_STOPWORDS for t in set(tokens)):
            return True

        return False

    def load_reviews_from_file(self, file_path: str, reference_date: Optional[datetime] = None) -> List[SanitizedReview]:
        """
        Load reviews from a CSV or JSON export file, normalize (strip emojis),
        filter out Hindi and unclear reviews, sanitize PII, and return SanitizedReview objects.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Export file not found: {file_path}")

        ref_dt = reference_date or datetime.now(timezone.utc)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)

        max_window_delta = timedelta(weeks=self.config.time_window_max_weeks)
        cutoff_dt = ref_dt - max_window_delta
        midpoint_dt = ref_dt - timedelta(weeks=(self.config.time_window_min_weeks + self.config.time_window_max_weeks) / 2.0)

        raw_records = self._parse_file(file_path)
        sanitized_reviews = []
        rejected_count = 0

        for idx, rec in enumerate(raw_records):
            try:
                # Extract fields
                rev_id = str(rec.get("review_id", f"rev_{idx}")).strip()
                store = str(rec.get("store", "GOOGLE_PLAY")).strip().upper()
                user_name_raw = str(rec.get("user_name") or rec.get("userName") or rec.get("author") or "Anonymous").strip()
                rating_raw = rec.get("rating", 3)
                rating = int(float(rating_raw)) if rating_raw is not None else 3
                title = str(rec.get("title", "")).strip()
                body = str(rec.get("body", "")).strip()

                # Rule 2: Ignore Emojis (normalize by stripping before validation)
                title = self._strip_emojis(title)
                body = self._strip_emojis(body)

                # Rule 1: Ignore Hindi reviews
                if self._is_hindi(title) or self._is_hindi(body):
                    rejected_count += 1
                    continue

                # Rule 3: Remove reviews with unclear meaning / spam
                if self._is_unclear(title, body):
                    rejected_count += 1
                    continue

                # Parse timestamp or impute if missing/malformed
                submitted_at_raw = rec.get("submitted_at")
                imputed = False
                submitted_dt = self._parse_timestamp(submitted_at_raw)
                
                if submitted_dt is None:
                    submitted_dt = midpoint_dt
                    imputed = True
                elif submitted_dt < cutoff_dt or submitted_dt > ref_dt:
                    # Outside time window
                    rejected_count += 1
                    continue

                # Run PII scrubber on normalized text
                scrubbed_title = self.scrubber.scrub(title)
                scrubbed_body = self.scrubber.scrub(body)
                scrubbed_user_name = self.scrubber.scrub(user_name_raw) or "Anonymous"

                review = SanitizedReview(
                    review_id=rev_id,
                    store=store,
                    user_name=scrubbed_user_name,
                    rating=rating,
                    title=scrubbed_title,
                    body=scrubbed_body,
                    submitted_at=submitted_dt,
                    is_pii_scrubbed=True,
                    imputed_timestamp=imputed,
                )
                sanitized_reviews.append(review)
            except Exception as e:
                self.logger.warning(f"Error processing review record index {idx}: {str(e)}")
                rejected_count += 1

        self.logger.info(
            f"Ingestion complete for {file_path}. Loaded: {len(sanitized_reviews)}, Rejected/Filtered: {rejected_count}"
        )
        return sanitized_reviews

    def _parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse CSV or JSON file into a list of dictionaries."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "reviews" in data:
                    return data["reviews"]
                else:
                    raise ValueError("JSON file must contain a list of review objects or a 'reviews' key.")
        elif ext == ".csv":
            records = []
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    norm_row = {k.lower().strip(): v for k, v in row.items() if k}
                    records.append(norm_row)
            return records
        else:
            raise ValueError(f"Unsupported export format: {ext}. Only .csv and .json are supported.")

    def _parse_timestamp(self, ts_val: Any) -> Optional[datetime]:
        """Attempt to parse ISO strings or timestamps into timezone-aware UTC datetime."""
        if not ts_val:
            return None
        if isinstance(ts_val, datetime):
            if ts_val.tzinfo is None:
                return ts_val.replace(tzinfo=timezone.utc)
            return ts_val.astimezone(timezone.utc)
        
        ts_str = str(ts_val).strip()
        formats = [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(ts_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
        return None
