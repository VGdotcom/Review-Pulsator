# Review Pulsator — Edge Cases, Corner Scenarios & Mitigation Strategy

This document (`Edge-case.md`) identifies the critical edge cases, corner scenarios, and potential failure modes across the **Review Pulsator** pipeline. Developed as a companion to [Context.md](file:///Users/vkg/Desktop/Review%20Pulsator/Docs/Context.md), [Architecture.md](file:///Users/vkg/Desktop/Review%20Pulsator/Docs/Architecture.md), and [implementation-plan.md](file:///Users/vkg/Desktop/Review%20Pulsator/Docs/implementation-plan.md), this specification defines deterministic mitigation strategies and fallback behaviors to ensure system resilience, data privacy, and SLA compliance.

---

## 1. Ingestion & Preprocessing Layer Scenarios

### 1.1. Zero Reviews in the Time Window (Empty Dataset)
- **Scenario**: An application receives zero public reviews during the target 8–12 week sliding window (common for niche B2B apps or stable legacy releases).
- **Failure Mode**: Downstream embedding and clustering algorithms crash due to division by zero or empty array indexing; LLM attempts to hallucinate themes from empty context.
- **Mitigation & Fallback**:
  - The `IngestionService` checks total ingested count prior to sanitization.
  - If `review_count == 0`, the pipeline short-circuits execution and generates a standardized **"Zero-Signal Pulse"** payload:
    ```json
    {
      "report_date": "2026-07-05",
      "word_count": 45,
      "top_themes": [{ "name": "No Volume", "summary": "No public reviews were recorded during the last 8–12 weeks." }],
      "verbatim_quotes": ["No verbatim quotes available for this period."],
      "action_ideas": ["Verify app store indexing and review export pipeline health.", "Consider prompting engaged users for feedback via in-app review requests."]
    }
    ```
  - The MCP delivery layer publishes this notice to Google Docs and drafts the notification email without throwing an error.

### 1.2. Massive Volume Spike / Review Bombing
- **Scenario**: A viral bug, PR crisis, or review bombing event results in an influx of $>50,000$ reviews in a single week.
- **Failure Mode**: Memory exhaustion during ingestion, embedding API rate-limit throttling (HTTP 429), and LLM token context window overflow.
- **Mitigation & Fallback**:
  - **Stratified Sampling**: If `review_count > 5,000`, the engine implements stratified random sampling balanced across star ratings (1-star to 5-star) and review timestamps to cap the clustering dataset at exactly 5,000 representative reviews.
  - **Batching & Throttling**: Embedding generation is chunked into batches of 250 items with exponential backoff on HTTP 429 rate-limit errors.

### 1.3. Malformed Exports & Corrupted Encoding
- **Scenario**: Store exports contain broken CSV encapsulation, missing submission timestamps, or non-standard character encoding (e.g., emojis, Zalgo text, HTML tags in review bodies).
- **Mitigation & Fallback**:
  - The ingestion parser applies UTF-8 strict normalization, strips HTML tags using a fast regex/DOM parser, and replaces emojis with ASCII spacing.
  - Rows missing timestamps default to `report_date - 4 weeks` (midpoint of window) and are tagged with `imputed_timestamp: true`.

### 1.4. Multilingual & Code-Switched Feedback
- **Scenario**: Reviews are written in non-target languages or mixed dialects (e.g., Spanglish, Hinglish).
- **Mitigation & Fallback**:
  - Implement language identification (e.g., `langdetect` or `fasttext`).
  - Non-target language reviews are either translated via a fast offline translation model or grouped into a dedicated `"International User Feedback"` cluster if translation is disabled.

---

## 2. PII Scrubbing & Sanitization Corner Cases

### 2.1. Obfuscated & Adversarial PII
- **Scenario**: Users intentionally obfuscate sensitive data to bypass store filters (e.g., spelling out numbers: `"call me at five five five zero one nine nine"`, or spacing emails: `"john . doe @ gmail . com"`).
- **Mitigation & Fallback**:
  - Implement normalization pre-passes: collapse whitespace around `@` and `.` tokens, and convert alphanumeric number words into digits prior to running regular expression regex scrubbers.

### 2.2. False Positive PII Removal
- **Scenario**: The NER or regex scrubber incorrectly identifies app version numbers, error codes, or product feature names as PII (e.g., `"iOS 17.4.1"` scrubbed as an IP address, or `"Error 404"` scrubbed as a phone number).
- **Mitigation & Fallback**:
  - Maintain an explicit **Domain Whitelist Dictionary** containing OS names, app version regex patterns (`v\d+\.\d+(\.\d+)?`), standard HTTP error codes, and proprietary brand terms. The scrubber checks tokens against the whitelist before applying replacement masks.

---

## 3. Clustering & Theming Engine Scenarios

### 3.1. Low Cluster Density (< 3 Emergent Themes)
- **Scenario**: The application only receives feedback on a single topic (e.g., 100% of reviews complain about GPS map tracking freezing during delivery), resulting in only 1 or 2 mathematically viable clusters.
- **Failure Mode**: System fails the structural requirement to report "Top 3 Themes".
- **Mitigation & Fallback**:
  - If distinct clusters $< 3$, the `ThemingEngine` dynamically splits the dominant cluster into sub-themes based on secondary keyword frequency (e.g., separating `"GPS Map Tracking Freeze on iOS"` from `"Live Delivery Status Lag on Android"`).
  - If splitting is impossible (total reviews $< 3$), the engine outputs the available themes and fills remaining slots with `"[No Additional Distinct Themes Detected]"`, ensuring schema validity without inventing artificial themes.

### 3.2. Uniform Sentiment & Volume Tie-Breaking
- **Scenario**: Multiple clusters have identical review counts and composite severity scores.
- **Mitigation & Fallback**:
  - Implement deterministic tie-breaking heuristics in the following order of precedence:
    1. **Recency Velocity**: Cluster with a higher percentage of reviews submitted within the last 7 days wins.
    2. **Rating Severity**: Cluster with a lower average star rating (e.g., 1.2 stars vs. 2.1 stars) wins.
    3. **Alphabetical Theme ID**: Final deterministic tie-breaker to ensure reproducible runs.

### 3.3. Dominance of Generic Noise ("Other / Unclassifiable")
- **Scenario**: A large volume of uninformative reviews (`"good"`, `"nice app"`, `"bad"`, `"fix this"`) forms the largest cluster.
- **Mitigation & Fallback**:
  - Reviews with token counts $< 4$ after stopword removal are routed to a `"Low-Information / Noise"` sink. This cluster is explicitly disqualified from ranking in the Top 3 themes regardless of volume.

---

## 4. Pulse Synthesis & LLM Guardrail Failures

### 4.1. Word Count Overflow (> 250 Words Ceiling)
- **Scenario**: The LLM consistently generates summaries exceeding the 250-word ceiling even after prompt instructions.
- **Mitigation & Fallback**:
  - **Self-Correction Retry**: The `PulseGenerator` feeds the output back to the LLM with the prompt: `"Your previous output was {N} words. Shorten it to <= 240 words while preserving all 3 quotes and 3 action items."` (Max 2 retries).
  - **Deterministic Pruning**: If retry limits are exhausted, a programmatic trimmer prunes descriptive adjectives from theme summaries and truncates action item explanations to their primary independent clause, guaranteeing the final output stays $\le 250$ words.

### 4.2. Verbatim Quote Hallucination or Paraphrasing
- **Scenario**: The LLM slightly modifies grammatical errors or paraphrases a user quote, failing the exact substring verification check against the `SanitizedReview` database.
- **Mitigation & Fallback**:
  - **Programmatic Centroid Extraction**: If quote verification fails after 2 LLM retries, the system bypasses the LLM for quote selection entirely. It programmatically selects the review sentence closest to the vector centroid of each Top 3 cluster, inserting it verbatim into the report payload.

### 4.3. Toxic, Profane, or Competitor-Slander Quotes
- **Scenario**: A representative verbatim quote contains profanity, hate speech, or defamatory competitor claims.
- **Mitigation & Fallback**:
  - Execute a fast profanity and toxicity filter (e.g., `better-profanity` or regex mask) on candidate quotes prior to selection. Profane words are masked with asterisks (e.g., `"This app is f***ing broken"`). If a quote exhibits hate speech or severe toxicity, it is discarded and the next closest centroid sentence is selected.

---

## 5. MCP Delivery & Workspace Integration Scenarios

### 5.1. MCP Server Unreachable or Timeout
- **Scenario**: The local Google Docs or Gmail MCP server is offline, unresponsive, or returns HTTP 500 / authentication errors during tool invocation.
- **Mitigation & Fallback**:
  - Implement exponential backoff retry logic (3 attempts: 2s, 4s, 8s delays).
  - **Offline Filesystem Archiving**: If the MCP server remains unreachable, the pipeline saves the `WeeklyPulseReport` payload to a persistent filesystem directory (`/archives/failed_mcp_delivery/pulse_YYYY_MM_DD.json`).
  - The orchestrator exits with a warning code (`EXIT_CODE_2_MCP_DEGRADED`) and prints a terminal notification alerting the developer to manually sync or check MCP daemon health.

### 5.2. Google Doc Permission Lock or Concurrent Edits
- **Scenario**: The target Google Doc is locked for editing by an administrator, or concurrent stakeholder edits cause update conflicts during `mcp_gdocs_update_doc`.
- **Mitigation & Fallback**:
  - Instead of overwriting or failing, the MCP client attempts to append a new top-level section dated `"[Pulse Report — YYYY-MM-DD]"`.
  - If write access is entirely denied (Permission Denied error), the client falls back to invoking `mcp_gdocs_create_doc` to generate a brand new timestamped document, updating the hyperlink in the Gmail draft accordingly.

### 5.3. Gmail Draft Quota / Invalid Alias
- **Scenario**: The designated email alias is invalid or the mailbox draft quota is exceeded.
- **Mitigation & Fallback**:
  - If the target alias fails validation, the MCP adapter defaults to drafting the email addressed directly to the authenticated Google Workspace user account running the MCP daemon.

---

## 6. Edge-Case Mitigation Summary Matrix

| Pipeline Layer | Corner Scenario | Primary Mitigation Strategy | Deterministic Fallback |
| :--- | :--- | :--- | :--- |
| **Ingestion** | Zero reviews in window | Short-circuit clustering | Generate "Zero-Signal Pulse" notice |
| **Ingestion** | Massive review bombing ($>50k$) | Stratified random sampling | Cap processing at 5,000 representative reviews |
| **Scrubbing** | Obfuscated PII (`"five five five..."`) | Pre-pass token/number normalization | Regex + NER multi-pass scrubber |
| **Scrubbing** | Brand/Version false positives | Domain whitelist checking | Preserve whitelisted terms (`iOS`, `v3.1`) |
| **Clustering** | Only 1 or 2 emergent themes | Dynamic sub-theme splitting | Insert `"[No Additional Themes Detected]"` |
| **Synthesis** | Word count $>250$ words | LLM self-correction prompt (2x) | Programmatic clause trimming to $\le 250$ words |
| **Synthesis** | Quote hallucination/paraphrase | Exact substring verification | Programmatic vector centroid quote extraction |
| **MCP Delivery** | MCP server down/unreachable | Exponential backoff retry | Local JSON archiving (`/archives/`) + warning exit |
| **MCP Delivery** | Doc locked / permission error | Append section instead of overwrite | Create new timestamped Google Doc via MCP |
