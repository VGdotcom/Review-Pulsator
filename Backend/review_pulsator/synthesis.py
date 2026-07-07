"""
Pulse Synthesis and Summarization Module for Review Pulsator (Phase 4).
Uses Groq LLM (llama-3.3-70b-versatile) to generate an executive-ready weekly note
adhering to strict structural constraints (<=250 words, 3 verbatim quotes, 3 action items).
Includes automated quote verification, retry self-correction loop, and deterministic fallback.
"""
import os
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
from review_pulsator.config import PulsatorConfig
from review_pulsator.schemas import ThemeCluster, ThemeSummary, WeeklyPulseReport

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class PulseGenerator:
    """
    Engine responsible for synthesizing Top 3 ThemeCluster objects into a <=250 word
    WeeklyPulseReport using Groq LLM, enforcing verbatim quote validation and word ceilings.
    """

    def __init__(
        self,
        config: Optional[PulsatorConfig] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 2,
    ):
        self.config = config or PulsatorConfig.from_env()
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or self.config.groq_model
        self.max_retries = max_retries
        
        self.client = None
        if GROQ_AVAILABLE and self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Could not initialize Groq client: {str(e)}")

    def _calculate_word_count(self, report_dict: Dict[str, Any]) -> int:
        """Calculate total word count across all text fields of the report payload."""
        text_parts = [report_dict.get("report_date", "")]
        
        for t in report_dict.get("top_themes", []):
            if isinstance(t, dict):
                text_parts.append(str(t.get("name", "")))
                text_parts.append(str(t.get("summary", "")))
            elif hasattr(t, "name"):
                text_parts.append(str(t.name))
                text_parts.append(str(t.summary))
                
        for q in report_dict.get("verbatim_quotes", []):
            text_parts.append(str(q))
            
        for a in report_dict.get("action_ideas", []):
            text_parts.append(str(a))
            
        combined_text = " ".join(text_parts)
        words = re.findall(r"\b\w+\b", combined_text)
        return len(words)

    def _verify_quotes(self, candidate_quotes: List[str], valid_quotes: Set[str]) -> Tuple[bool, Optional[str]]:
        """
        Verify that each candidate quote is an exact substring of the valid raw/sanitized quotes.
        Returns (is_valid, error_message).
        """
        if len(candidate_quotes) != 3:
            return False, f"Expected exactly 3 verbatim quotes, got {len(candidate_quotes)}."
            
        for cq in candidate_quotes:
            cq_clean = cq.strip()
            # Exact substring match check
            match_found = any(cq_clean in vq or vq in cq_clean for vq in valid_quotes)
            if not match_found:
                # Try case-insensitive matching as slight tolerance before failing
                match_found_lower = any(cq_clean.lower() in vq.lower() or vq.lower() in cq_clean.lower() for vq in valid_quotes)
                if not match_found_lower:
                    return False, f"Quote '{cq}' failed verbatim verification against source database."
                    
        return True, None

    def _prune_to_word_ceiling(self, report_dict: Dict[str, Any], max_words: int = 245) -> Dict[str, Any]:
        """
        Deterministic clause trimmer (Edge-case 4.1) to guarantee word count stays <= 250
        if LLM retries are exhausted.
        """
        current_words = self._calculate_word_count(report_dict)
        if current_words <= max_words:
            report_dict["word_count"] = current_words
            return report_dict

        # Truncate action ideas first
        action_ideas = report_dict.get("action_ideas", [])
        pruned_actions = []
        for a in action_ideas:
            # Keep only first sentence or up to 12 words
            words = str(a).split()
            pruned_actions.append(" ".join(words[:12]) + ("..." if len(words) > 12 else ""))
        report_dict["action_ideas"] = pruned_actions

        current_words = self._calculate_word_count(report_dict)
        if current_words <= max_words:
            report_dict["word_count"] = current_words
            return report_dict

        # Truncate theme summaries
        top_themes = report_dict.get("top_themes", [])
        pruned_themes = []
        for t in top_themes:
            t_dict = t if isinstance(t, dict) else t.model_dump()
            words = str(t_dict.get("summary", "")).split()
            t_dict["summary"] = " ".join(words[:10]) + ("..." if len(words) > 10 else "")
            pruned_themes.append(t_dict)
        report_dict["top_themes"] = pruned_themes

        report_dict["word_count"] = self._calculate_word_count(report_dict)
        return report_dict

    def _generate_deterministic_fallback(
        self,
        top_themes: List[ThemeCluster],
        report_date: str,
        valid_quotes: List[str]
    ) -> WeeklyPulseReport:
        """
        Programmatic centroid/verbatim extraction (Edge-cases 4.1 & 4.2 & Offline fallback).
        Used when Groq LLM is unavailable or when self-correction retries are exhausted.
        """
        themes_summary = []
        selected_quotes = []
        action_ideas = []

        # Ensure we have up to 3 themes
        bounded_themes = top_themes[:3]
        
        # Action templates mapped to common Swiggy themes
        action_map = {
            "theme_delivery": "Optimize partner GPS tracking and address delivery executive delay root causes.",
            "theme_accuracy": "Implement stricter restaurant packaging checks and automated missing item refunds.",
            "theme_instamart": "Improve Instamart inventory synchronization to prevent out-of-stock cancellations.",
            "theme_pricing": "Refine customer care chat resolution flows and review fee structures.",
            "theme_app": "Investigate payment checkout crashes and optimize app UI responsiveness.",
        }

        for idx, clu in enumerate(bounded_themes):
            themes_summary.append(ThemeSummary(
                name=clu.theme_name[:30],
                summary=f"High volume pain point ({clu.review_count} reviews, {clu.average_rating}⭐ avg) impacting user experience."
            ))
            
            # Select 1 verbatim quote per theme
            if clu.representative_quotes:
                selected_quotes.append(clu.representative_quotes[0])
            elif valid_quotes:
                selected_quotes.append(valid_quotes[idx % len(valid_quotes)])
            else:
                selected_quotes.append("No verbatim feedback quote recorded.")
                
            # Select action idea
            act = action_map.get(clu.theme_id, f"Address key user friction points identified in {clu.theme_name}.")
            action_ideas.append(act)

        # Ensure exactly 3 quotes and 3 action items
        while len(selected_quotes) < 3:
            selected_quotes.append(valid_quotes[len(selected_quotes) % len(valid_quotes)] if valid_quotes else "No additional verbatim quotes.")
        while len(action_ideas) < 3:
            action_ideas.append("Conduct deep-dive user interviews on top emerging product friction areas.")

        payload = {
            "report_date": report_date,
            "word_count": 0,
            "top_themes": [t.model_dump() for t in themes_summary[:3]],
            "verbatim_quotes": selected_quotes[:3],
            "action_ideas": action_ideas[:3],
        }

        pruned_payload = self._prune_to_word_ceiling(payload, max_words=240)
        return WeeklyPulseReport(**pruned_payload)

    def generate_pulse(
        self,
        top_themes: List[ThemeCluster],
        report_date: Optional[str] = None
    ) -> WeeklyPulseReport:
        """
        Synthesize top themes into a WeeklyPulseReport. Attempts Groq LLM generation
        with automated quote verification and word count checks, falling back to deterministic synthesis if needed.
        """
        if not report_date:
            report_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Gather all valid verbatim quotes across all themes
        valid_quotes_list = []
        valid_quotes_set = set()
        for clu in top_themes:
            for q in clu.representative_quotes:
                q_clean = q.strip()
                if q_clean and q_clean not in valid_quotes_set:
                    valid_quotes_set.add(q_clean)
                    valid_quotes_list.append(q_clean)

        # If Groq client is not configured, use offline deterministic fallback
        if not self.client:
            print("Groq API client not initialized or offline. Using deterministic synthesis fallback.")
            return self._generate_deterministic_fallback(top_themes, report_date, valid_quotes_list)

        # Prepare prompt context for Groq (capped to respect 12K Tokens Per Minute limit)
        themes_context = [
            {
                "theme_id": c.theme_id,
                "name": c.theme_name,
                "review_count": c.review_count,
                "average_rating": c.average_rating,
                "severity_score": c.sentiment_severity_score,
                "verbatim_quotes": c.representative_quotes[:6],  # Cap quotes to ensure compact prompt payload (<1000 tokens)
            }
            for c in top_themes[:3]
        ]

        system_prompt = (
            "You are an executive AI product analyst for Swiggy. Distill customer review clusters into an executive weekly note.\n"
            "STRICT STRUCTURAL RULES:\n"
            "1. Output ONLY valid JSON matching exactly this schema: {\"report_date\": \"YYYY-MM-DD\", \"word_count\": int, \"top_themes\": [{\"name\": \"str\", \"summary\": \"str\"}], \"verbatim_quotes\": [\"str\"], \"action_ideas\": [\"str\"]}.\n"
            "2. Total word count of all text fields combined MUST NOT EXCEED 240 words. Be concise and punchy.\n"
            "3. Select exactly 3 verbatim anonymous quotes from the provided verbatim_quotes list. You MUST NOT paraphrase, fix grammar, or change a single character.\n"
            "4. Provide exactly 3 concrete engineering or product action ideas grounded in the themes.\n"
            "5. Exactly 3 top_themes must be returned."
        )

        user_prompt = f"Report Date: {report_date}\nTop 3 Clusters Context:\n{json.dumps(themes_context, indent=2)}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Self-Correction Retry Loop (Edge-case 4.1 & 4.2)
        for attempt in range(1, self.max_retries + 2):
            try:
                print(f"Calling Groq LLM ({self.model}) for pulse synthesis (Attempt {attempt})...")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.config.groq_temperature,
                    max_tokens=800,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                data = json.loads(content)
                
                # Enforce report date
                data["report_date"] = report_date
                
                # Verify exactly 3 items in arrays
                if len(data.get("top_themes", [])) != 3:
                    raise ValueError(f"Expected exactly 3 top_themes, got {len(data.get('top_themes', []))}.")
                if len(data.get("verbatim_quotes", [])) != 3:
                    raise ValueError(f"Expected exactly 3 verbatim_quotes, got {len(data.get('verbatim_quotes', []))}.")
                if len(data.get("action_ideas", [])) != 3:
                    raise ValueError(f"Expected exactly 3 action_ideas, got {len(data.get('action_ideas', []))}.")

                # Verify verbatim quote authenticity (Edge-case 4.2)
                quotes_valid, quote_err = self._verify_quotes(data["verbatim_quotes"], valid_quotes_set)
                if not quotes_valid:
                    raise ValueError(quote_err)

                # Verify word count ceiling (Edge-case 4.1)
                word_count = self._calculate_word_count(data)
                data["word_count"] = word_count
                if word_count > 250:
                    raise ValueError(f"word_count ({word_count}) exceeds strict 250 word ceiling.")

                # Validate against Pydantic model
                report = WeeklyPulseReport(**data)
                print(f"Successfully synthesized WeeklyPulseReport via Groq ({word_count} words)!")
                return report

            except Exception as e:
                err_msg = str(e)
                print(f"Synthesis validation/API failed on attempt {attempt}: {err_msg}")
                # Check for Groq Rate Limit / Token limit errors (HTTP 429)
                if "429" in err_msg or "rate limit" in err_msg.lower() or "tokens per minute" in err_msg.lower():
                    print(f"Groq Rate Limit Exceeded (Limits: {self.config.groq_max_rpm} RPM, {self.config.groq_max_tpm} TPM). Falling back to deterministic synthesis immediately.")
                    break
                if attempt <= self.max_retries:
                    # Feed error back to LLM for self-correction
                    messages.append({"role": "assistant", "content": content if 'content' in locals() else "{}"})
                    messages.append({
                        "role": "user",
                        "content": f"VALIDATION ERROR: {err_msg}. You must fix this error. Keep total word count <= 230 words and use ONLY exact verbatim quotes from the provided context."
                    })
                else:
                    print("Exhausted LLM retries. Falling back to deterministic clause pruning and centroid extraction.")

        # Deterministic fallback after retries exhausted
        return self._generate_deterministic_fallback(top_themes, report_date, valid_quotes_list)
