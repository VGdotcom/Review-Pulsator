# Review Pulsator — Operational Runbook & Walkthrough

This document serves as the operational guide and technical walkthrough for the **Review Pulsator** pipeline. With the completion of Phase 6, the system delivers an end-to-end, privacy-compliant AI summarization engine that transforms raw app store reviews into executive weekly insights delivered via Google Workspace (Docs & Gmail).

---

## 1. Architecture Overview

```
+-------------------+       +-------------------+       +--------------------+
|  Raw Review Data  | ----> |  Ingestion Engine | ----> | PII Scrubber (NER) |
| (App/Play Stores) |       | (8-12 Week Filter)|       | Zero PII Leakage   |
+-------------------+       +-------------------+       +--------------------+
                                                                  |
                                                                  v
+-------------------+       +-------------------+       +--------------------+
|  Google Workspace | <---- |   Synthesis LLM   | <---- | Bounded Clustering |
|  (Docs / Gmail)   |       |  (Groq 70B / 250w)|       |  (Max 5 / Top 3)   |
+-------------------+       +-------------------+       +--------------------+
```

### Key System Guardrails
1. **Time-Window Filtering**: Reviews older than 12 weeks or newer than 8 weeks are automatically discarded to maintain focus on emerging trends.
2. **Zero PII Leakage**: Multi-pass regex and Named Entity Recognition (NER) anonymization strips names, emails, phone numbers, usernames, and device IDs before vectorization or LLM prompting.
3. **Bounded Theming**: Reviews are clustered into at most **5 domain themes** (mapped to Swiggy taxonomies), with exactly the **Top 3 drivers** selected based on volume and sentiment severity.
4. **Strict Word Ceiling ($\le 250$ Words)**: Post-synthesis validators enforce word limits and exact substring verification for 3 verbatim customer quotes.
5. **Resilient Workspace Delivery**: Publishes styled reports to Google Docs and creates draft notifications in Gmail via Model Context Protocol (MCP), featuring exponential backoff and local offline backup archiving.

---

## 2. Command Line Interface (CLI) Usage

The system is controlled via the central CLI entrypoint `main.py` (or `python -m review_pulsator`).

### Basic Command Syntax
```bash
# Activate virtual environment
source .venv/bin/activate

# Display CLI options and help
python main.py --help
```

### Running in Dry-Run Mode (Recommended for Local Testing)
Dry-run mode executes the full data extraction, PII scrubbing, clustering, and Groq LLM synthesis without invoking remote MCP tools. Artifacts are generated and stored locally:
```bash
python main.py --dry-run --input data/swiggy_reviews.json
```
**Generated Artifacts:**
- `archives/dry_run_reports/pulse_YYYY-MM-DD.json`: Complete JSON report payload.
- `archives/dry_run_reports/pulse_YYYY-MM-DD.md`: Styled Markdown report formatted for Google Docs.
- `archives/dry_run_reports/pulse_YYYY-MM-DD.html`: Styled HTML summary formatted for Gmail notifications.

### Running Live E2E Pipeline with Workspace Delivery
To run the full pipeline and publish directly to Google Docs and Gmail:
```bash
python main.py --input data/swiggy_reviews.json --email exec@swiggy.in --doc-id <GOOGLE_DOC_ID>
```
*Note: If `--doc-id` is omitted, the MCP client will automatically create a new Google Document and return its URL.*

### 2.1 Interactive Web Dashboard Usage
The system includes a state-of-the-art interactive web dashboard (`dashboard_server.py`) for real-time visual sentiment exploration, Chart.js analytics, and one-click AI report synthesis.
```bash
# Launch interactive dashboard server on port 8080
python dashboard_server.py
```
Open your browser to **`http://localhost:8080/`** to:
- **Explore Visual Analytics**: Interactive donut charts for star rating breakdown and radar/bar charts for volume $\times$ severity indices across domain clusters.
- **Trigger Live AI Pulse**: Click the glowing primary button to execute real-time Groq Llama 3.3 70B vectorization and quote extraction directly from the UI.
- **Audit Historical Archives**: Browse, filter, and inspect past JSON/Markdown report archives.

---

## 3. Configuration & Environment Variables

All parameters are configured via `.env` in the project root:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | *(Required)* | API key for Groq Cloud LLM synthesis. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Target LLM model for synthesis. |
| `GROQ_TEMPERATURE` | `0.4` | Low temperature ensures deterministic formatting and verbatim accuracy. |
| `WORD_COUNT_CEILING` | `250` | Maximum allowable words for the weekly pulse report. |
| `MAX_THEMES` | `5` | Upper limit on generated semantic clusters. |
| `TOP_THEMES_COUNT` | `3` | Number of top themes extracted for executive reporting. |
| `TARGET_EMAIL` | `exec@swiggy.in` | Default recipient email address for Gmail notification drafts. |
| `GDOCS_DOC_ID` | `None` | Default Google Doc ID for recurring report appends. |

---

## 4. Automation & Cron Scheduling

To automate weekly pulse reporting (e.g., every Monday at 8:00 AM UTC), add the following job to your system crontab:

```cron
# Edit crontab via `crontab -e`
0 8 * * 1 cd "/Users/vkg/Desktop/Review Pulsator" && /Users/vkg/Desktop/Review Pulsator/.venv/bin/python main.py --input data/swiggy_reviews.json >> /Users/vkg/Desktop/Review Pulsator/archives/cron_pipeline.log 2>&1
```

---

## 5. Verification & Test Suite

The project includes an automated unit and E2E test suite covering all 6 phases of implementation.

### Executing Tests
```bash
source .venv/bin/activate
pytest tests/ -v
```

### Test Coverage Summary (38 Tests Passing)
- **`test_config.py`**: Verifies configuration loading, environment variable overrides, and logging formatters.
- **`test_schemas.py`**: Validates strict data contracts for raw reviews, scrubbed reviews, theme clusters, and final pulse reports.
- **`test_ingestion.py`**: Validates CSV/JSON parsers, time-window window filtering, timestamp imputation, and Hindi/emoji cleaning rules.
- **`test_scrubber.py`**: Validates zero PII leakage for emails, obfuscated emails, phone numbers, usernames, and device UUIDs/IPs.
- **`test_clustering.py`**: Validates bounded clustering ($\le 5$ themes), Swiggy taxonomy mapping, volume/severity ranking, and noise padding.
- **`test_synthesis.py`**: Validates Groq prompt formatting, verbatim quote verification, word ceiling pruning, retry loops, and deterministic offline fallbacks.
- **`test_delivery.py`**: Validates Google Docs Markdown formatting, Gmail HTML styling, MCP retry resilience, and offline backup archiving.
- **`test_cli.py`**: Validates E2E CLI orchestration, argument parsing, dry-run filesystem generation, and mock MCP tool execution.

---

## 6. Troubleshooting & Fault Tolerance

1. **Groq Rate Limit Exceeded (429 / TPM Limit)**:
   - *Symptom*: LLM API raises HTTP 429 Rate Limit Error.
   - *Resolution*: The `PulseGenerator` automatically implements exponential backoff and quote context pruning (capping candidate sentences to top 6) to stay within the 12K TPM limit. If retries are exhausted, it seamlessly falls back to deterministic extractive synthesis.
2. **MCP Workspace Server Unavailable**:
   - *Symptom*: Cannot reach Google Workspace MCP server (`mcp_gdocs_create_doc` fails).
   - *Resolution*: The `MCPIntegrationService` automatically catches the connection failure, triggers an administrative alert in stdout, and saves the complete report package to `archives/failed_mcp_delivery/pulse_YYYY-MM-DD.json` for manual or scheduled re-delivery.
3. **No Reviews in Window**:
   - *Symptom*: Pipeline exits during Stage 1 with `No valid reviews remained`.
   - *Resolution*: Verify that your raw export file contains timestamps within the current sliding window (`8–12 weeks ago`).
