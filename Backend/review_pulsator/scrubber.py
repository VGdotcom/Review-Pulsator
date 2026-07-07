"""
Multi-pass PII scrubbing and text sanitization engine for Review Pulsator.
"""
import re
import html
from typing import Set


class PIIScrubber:
    """
    Multi-pass sanitization engine that strips HTML, normalizes text,
    protects whitelisted domain terms, and scrubs Personally Identifiable Information (PII).
    """

    # Domain whitelist to prevent false positive scrubbing (OS names, version patterns, error codes, Swiggy brand terms)
    DEFAULT_WHITELIST: Set[str] = {
        "ios", "android", "macos", "windows", "linux",
        "error 400", "error 401", "error 403", "error 404", "error 500", "error 502", "error 503",
        "http", "https", "url", "uri", "id", "kyc", "pin", "otp",
        "swiggy", "instamart", "dineout", "genie", "swiggy one", "upi", "valet", "zomato",
    }

    def __init__(self, custom_whitelist: Set[str] = None):
        self.whitelist = self.DEFAULT_WHITELIST.copy()
        if custom_whitelist:
            self.whitelist.update({w.lower() for w in custom_whitelist})

        # Regex patterns for obfuscated PII normalization
        self.spaced_email_pattern = re.compile(r'\b([a-zA-Z0-9_.+-]+)\s*@\s*([a-zA-Z0-9-]+)\s*\.\s*([a-zA-Z0-9-.]+)\b')
        
        # Regex patterns for PII detection
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.phone_pattern = re.compile(r'\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b|\b\d{3}[-. ]\d{4}\b')
        self.uuid_pattern = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
        self.ipv4_pattern = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
        self.mac_pattern = re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b')
        self.username_pattern = re.compile(r'@[a-zA-Z0-9_]{3,}\b')

        # Version regex to protect from IP/number matching (e.g. v3.14.1 or 2.0.4 - max 3 parts)
        self.version_pattern = re.compile(r'\b(v?\d{1,3}\.\d{1,3}(?:\.\d{1,3})?)\b', re.IGNORECASE)

    def scrub(self, text: str) -> str:
        """
        Execute the multi-pass sanitization pipeline on input text.
        """
        if not text:
            return ""

        # Pass 1: HTML unescaping and tag stripping
        cleaned = html.unescape(text)
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
        cleaned = " ".join(cleaned.split())  # normalize whitespace

        # Pass 2: Pre-pass normalization for obfuscated PII (e.g., spaced emails)
        cleaned = self.spaced_email_pattern.sub(r'\1@\2.\3', cleaned)

        # Pass 3: Scrub high-priority unambiguous PII first (Emails, UUIDs, IPv4s, MACs)
        cleaned = self.email_pattern.sub("[ANONYMIZED_EMAIL]", cleaned)
        cleaned = self.uuid_pattern.sub("[ANONYMIZED_DEVICE]", cleaned)
        cleaned = self.ipv4_pattern.sub("[ANONYMIZED_DEVICE]", cleaned)
        cleaned = self.mac_pattern.sub("[ANONYMIZED_DEVICE]", cleaned)

        # Pass 4: Protect whitelisted terms and version numbers using temporary tokens
        protected_tokens = {}
        counter = 0

        def protect_version(match):
            nonlocal counter
            val = match.group(0)
            token = f"__PROT_VER_{counter}__"
            protected_tokens[token] = val
            counter += 1
            return token

        cleaned = self.version_pattern.sub(protect_version, cleaned)

        for term in sorted(self.whitelist, key=len, reverse=True):
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            def protect_whitelist(match):
                nonlocal counter
                val = match.group(0)
                token = f"__PROT_WHT_{counter}__"
                protected_tokens[token] = val
                counter += 1
                return token
            cleaned = pattern.sub(protect_whitelist, cleaned)

        # Pass 5: Scrub secondary PII (Phone numbers, Usernames)
        cleaned = self.phone_pattern.sub("[ANONYMIZED_PHONE]", cleaned)
        cleaned = self.username_pattern.sub("[ANONYMIZED_USER]", cleaned)

        # Pass 6: Restore protected whitelisted terms and version numbers
        for token, orig_val in protected_tokens.items():
            cleaned = cleaned.replace(token, orig_val)

        return cleaned.strip()
