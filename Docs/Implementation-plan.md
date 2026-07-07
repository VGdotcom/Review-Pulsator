# Review Pulsator — Phase-Wise Implementation Plan

This document (`implementation-plan.md`) translates the architectural blueprints from [Architecture.md](file:///Users/vkg/Desktop/Review%20Pulsator/Docs/Architecture.md) and domain constraints from [Context.md](file:///Users/vkg/Desktop/Review%20Pulsator/Docs/Context.md) into an actionable, structured, phase-wise roadmap for engineering delivery.

---

## Executive Summary & Delivery Approach

The development of Review Pulsator is structured into **six incremental phases**. Each phase delivers a standalone, verifiable module of the pipeline, ensuring strict adherence to project guardrails: zero PII leakage, bounded clustering (max 5 themes / top 3 highlighted), strict word count ($\le 250$ words), verbatim quote authenticity, and Model Context Protocol (MCP) integration for Google Docs and Gmail.

---

## Phase 1: Project Setup, Core Schemas & Foundations

### Objectives
Establish the repository structure, dependency management, configuration loader, and core data schemas that define data contracts across all modules.

### Detailed Tasks
1. **Repository & Environment Initialization**:
   - Set up project dependency structure (e.g., Python virtual environment with `pyproject.toml` or Node.js project).
   - Configure code formatting, linting, and pre-commit hooks.
2. **Core Schema Implementation**:
   - Define data models using robust validation libraries (e.g., Pydantic or Zod):
     - `RawReview`: Schema representing raw export data (store type, star rating, title, body, timestamp).
     - `SanitizedReview`: Schema adding `is_pii_scrubbed` boolean flag and sanitized text.
     - `ThemeCluster`: Schema representing cluster metrics, representative quotes, and volume/rank.
     - `WeeklyPulseReport`: Final JSON payload containing word count, top 3 themes, 3 verbatim quotes, and 3 action items.
3. **Configuration & Logging Framework**:
   - Implement central configuration management (loading time-window parameters: default `8–12 weeks`, target theme limits: `max 5`, and output word ceiling: `250`).
   - Implement structured JSON logging for observability across pipeline execution stages.

### Deliverables & Verification
- [x] Schema models verified with unit tests testing valid/invalid payloads.
- [x] Config loader verified against sample environment variables.

---

## Phase 2: Ingestion & PII Scrubbing Pipeline (`IngestionService`)

### Objectives
Build the ingestion engine capable of reading public app store review exports and executing a rigorous PII sanitization pipeline before downstream processing.

### Detailed Tasks
1. **Public Store Export Connectors**:
   - Build parsers for Apple App Store and Google Play Store public review exports (CSV/JSON format support).
   - Implement time-window filtering to strictly retain reviews submitted within the last **8 to 12 weeks**.
   - Implement spam and empty-body rejection filters.
2. **PII Scrubbing Pipeline**:
   - Build a multi-pass sanitization engine combining regular expressions and Named Entity Recognition (NER).
   - Scrub and replace sensitive patterns:
     - Email addresses $\to$ `[ANONYMIZED_EMAIL]`
     - Phone numbers $\to$ `[ANONYMIZED_PHONE]`
     - Usernames / Proper names $\to$ `[ANONYMIZED_USER]`
     - IP / Device identifiers $\to$ `[ANONYMIZED_DEVICE]`
3. **Sanitization Audit Unit Tests**:
   - Create synthetic test datasets containing heavy PII injection to verify 100% removal efficacy without altering core sentiment keywords.

### Deliverables & Verification
- [x] Ingestion module successfully loads 8–12 week review exports.
- [x] PII scrubbing test suite passes with zero PII leakage detected across synthetic test fixtures.

---

## Phase 3: Clustering & Theming Engine (`ThemingEngine`)

### Objectives
Implement semantic vectorization and bounded clustering to categorize reviews into domain themes and extract the Top 3 sentiment drivers.

### Detailed Tasks
1. **Embedding & Vectorization**:
   - Integrate an embedding generation service (local lightweight transformers or API embeddings) to convert sanitized review bodies into dense semantic vectors.
2. **Bounded Clustering Algorithm**:
   - Implement clustering logic (e.g., K-Means, HDBSCAN, or LLM zero-shot categorization) explicitly bounded to a **maximum of 5 themes**.
   - Map clusters to Swiggy domain taxonomies (e.g., *Delivery Speed & Partner Behavior, Order Accuracy & Packaging, Instamart & Grocery Availability, Pricing & Swiggy One Coupons, App Performance & GPS Tracking*).
3. **Theme Scoring & Top 3 Extraction**:
   - Implement the ranking mathematical formulation: $\text{Score} = \text{Volume} \times \text{SentimentSeverityWeight}$.
   - Sort clusters and extract exactly the **Top 3 scoring clusters** for downstream synthesis.

### Deliverables & Verification
- [x] Clustering engine correctly groups reviews into $\le 5$ themes.
- [x] Ranker accurately outputs the Top 3 themes with corresponding review counts and sentiment scores.

---

## Phase 4: Pulse Synthesis & Summarization Module (`PulseGenerator`)

### Objectives
Develop the LLM summarization engine that distills the Top 3 clusters into an executive-ready weekly note adhering to strict structural and word-count constraints.

### Detailed Tasks
1. **Prompt Engineering & System Instructions**:
   - Construct a structured prompt enforcing:
     - **Word Count Ceiling**: $\le 250$ words total.
     - **Top 3 Themes**: Detailed summary of primary user pain points.
     - **Real User Quotes**: Exactly 3 verbatim review sentences extracted from the cluster data.
     - **Action Ideas**: Exactly 3 concrete engineering or product recommendations grounded in the themes.
2. **Output Validator & Quote Verification Engine**:
   - Build an automated post-processing validator that:
     - Counts total words and triggers an error if words $> 250$.
     - Performs exact substring verification for each returned quote against the `SanitizedReview` database to prevent LLM hallucination or paraphrasing.
3. **Self-Correction & Retry Loop**:
   - Implement a retry mechanism (up to 3 attempts) that feeds validation errors back to the LLM if word limits or verbatim quote checks fail.
   - Implement a fallback mechanism that selects top scoring raw sentences if quote verification fails after maximum retries.

### Deliverables & Verification
- [x] Synthesis module outputs valid `WeeklyPulseReport` JSON.
- [x] Validator confirms 100% verbatim quote matching and adherence to $\le 250$ words.

---

## Phase 5: MCP Delivery & Workspace Integration (`MCPIntegrationService`)

### Objectives
Integrate Model Context Protocol (MCP) tool calls to publish the weekly note to Google Docs and create a notification draft in Gmail without custom OAuth/REST boilerplate.

### Detailed Tasks
1. **Google Docs MCP Client Integration**:
   - Build an MCP adapter that converts `WeeklyPulseReport` JSON into styled markdown/document format (headers, bullet points, blockquotes).
   - Implement tool calling for `mcp_gdocs_create_doc` (for initial publication) and `mcp_gdocs_update_doc` (for recurring updates).
2. **Gmail MCP Client Integration**:
   - Build an email formatter generating clean HTML or plain text containing the pulse summary and a direct hyperlink to the Google Doc.
   - Implement tool calling for `mcp_gmail_create_draft` addressed to the user or designated team alias.
3. **Offline Archiving & Fault Tolerance**:
   - Add resilience logic: if an MCP server is unreachable, save the output payload to a local filesystem archive (`/archives/pulse_YYYY_MM_DD.json`) and log an administrative alert.

### Deliverables & Verification
- [x] End-to-end test successfully calls Google Docs MCP tool and verifies document creation/update.
- [x] End-to-end test successfully calls Gmail MCP tool and verifies draft creation in target mailbox.

---

## Phase 6: End-to-End Orchestration, Testing & Walkthrough

### Objectives
Assemble the individual modules into a unified command-line orchestrator or scheduled pipeline, conduct full system testing, and finalize documentation.

### Detailed Tasks
1. **Pipeline Orchestrator (`main.py` / CLI)**:
   - Create the central entrypoint orchestrating:
     $$\text{Ingestion} \longrightarrow \text{PII Scrubbing} \longrightarrow \text{Clustering} \longrightarrow \text{Synthesis} \longrightarrow \text{MCP Delivery}$$
   - Add CLI flags for dry-run mode (skipping MCP delivery) and custom date ranges.
2. **End-to-End Integration Testing**:
   - Execute end-to-end pipeline runs using sample App Store and Play Store review datasets.
   - Verify all logs, metrics, and final Google Workspace artifacts.
3. **Documentation & Walkthrough**:
   - Create user instructions and operational documentation summarizing how to execute the pipeline locally or schedule it via cron/schedulers.

### Deliverables & Verification
- [x] Fully functional end-to-end pipeline executing in under 60 seconds for standard review volumes.
- [x] Complete project documentation and operational runbooks.

---

## Phase 7: Production Deployment & Google Stitch Frontend Integration (Post-MVP)

### Objectives
Establish automated production containerization (Docker / Hugging Face Spaces), configure Vercel frontend hosting, and integrate a next-generation UI frontend using **Google Stitch**.

### Detailed Tasks
1. **Containerization & Cloud Hosting (`Deployment-plan.md`)**:
   - Package the backend engine into a multi-stage Docker container (`python:3.12-slim`, UID 1000, Port 7860) optimized for **Hugging Face Spaces**.
   - Configure Vercel static frontend deployment (`vercel.json`) with proxy rewrite rules to forward `/api/*` requests to the Hugging Face Spaces backend.
   - Set up secure secret injection (`GROQ_API_KEY`, `PULSATOR_GDOCS_DOC_ID`, `MCP_SERVER_URL`) via environment variables.
2. **Google Stitch Frontend Development**:
   - Built reactive, modern UI components matching Google Stitch SaaS mockups (Bento grids, sentiment bars, interactive tabs).
   - Wired up live REST APIs (`/api/status`, `/api/report`, `/api/analytics`, `/api/trigger_pulse`) with configurable `API_BASE` routing.
   - Created interactive taxonomy display cards and verbatim quote previews.

### Deliverables & Verification
- [x] Complete production deployment blueprint ([Deployment-plan.md](file:///Users/vkg/Desktop/Review%20Pulsator/Docs/Deployment-plan.md)).
- [x] Automated container builds (`Dockerfile`, `.dockerignore`, `README.md`) for **Hugging Face Spaces**.
- [x] Frontend hosting configuration (`vercel.json`) for **Vercel**.
- [x] Google Stitch frontend integrated with live backend REST APIs (`index.html`, `style.css`, `app.js`).

---

## Timeline & Milestone Summary

| Phase | Module / Milestone | Primary Focus | Success Criteria | Status |
| :---: | :--- | :--- | :--- | :---: |
| **Phase 1** | Foundations & Schemas | Repository setup, Pydantic/Zod schemas, Config loader | 100% schema validation test coverage | ✅ **DONE** |
| **Phase 2** | Ingestion & PII Scrubbing | Store export parsers, 8–12 week filter, NER/Regex PII scrubber | Zero PII leakage in audit tests | ✅ **DONE** |
| **Phase 3** | Clustering & Theming | Vector embeddings, $\le 5$ theme clustering, Top 3 ranker | Accurate grouping and ranking metrics | ✅ **DONE** |
| **Phase 4** | Pulse Synthesis | LLM prompt, $\le 250$ word check, verbatim quote verifier | Zero hallucinated quotes, strict word ceiling | ✅ **DONE** |
| **Phase 5** | MCP Delivery Layer | Google Docs MCP client, Gmail MCP client, Offline fallback | Document published & email draft created via MCP | ✅ **DONE** |
| **Phase 6** | Orchestration & Delivery | Unified CLI runner, E2E integration tests, Documentation | Seamless full-pipeline execution | ✅ **DONE** |
| **Phase 7** | **Google Stitch & Deploy** | Vercel Hosting, Hugging Face Dockerization, Stitch UI | Live cloud reporting & Stitch UI on Vercel/HF | ✅ **DONE** |
