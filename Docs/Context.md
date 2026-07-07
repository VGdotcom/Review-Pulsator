# Review Pulsator — Project Context & Architecture Guide

This document (`Context.md`) captures the foundational context, architectural principles, domain constraints, and workflow specifications for the **Review Pulsator** project. It serves as the authoritative reference for developers, AI assistants, and system integrators contributing to the codebase.

---

## 1. Project Overview & Core Purpose

**Review Pulsator** is an automated analytics and synthesis pipeline designed to transform raw user feedback from mobile app stores into a concise, actionable weekly pulse. 

Product teams, support specialists, and executive leadership often struggle with information overload when monitoring unstructured user reviews across the Apple App Store and Google Play Store. Review Pulsator solves this by automating the aggregation, clustering, synthesis, and distribution of user sentiment—delivering grounded insights directly to familiar collaboration workspaces (Google Docs and Gmail) without requiring manual review sifting or complex bespoke REST API wiring.

---

## 2. Target Stakeholders & Value Proposition

| Stakeholder Group | Primary Pain Point | Review Pulsator Value Proposition |
| :--- | :--- | :--- |
| **Product & Growth Teams** | Difficulty distinguishing critical usability bugs from feature requests at scale. | Delivers data-driven prioritization based on real user signals and recurring pain points rather than anecdotal assumptions. |
| **Customer Support** | Disconnect between internal help documentation and actual customer language. | Aligns support messaging and FAQs with the verbatim phrasing and sentiment users experience in production. |
| **Executive Leadership** | Drowning in raw reviews when trying to gauge product health. | Provides a rapid, one-page weekly health check (≤250 words) highlighting top trends and actionable next steps. |

---

## 3. End-to-End System Workflow

The Review Pulsator pipeline executes four sequential processing stages:

```mermaid
flowchart TD
    A[Public Review Exports<br>App Store / Play Store<br>8–12 Weeks Data] -->|Ingestion & Filtering| B[Preprocessing & Sanitization<br>PII Stripping]
    B -->|NLP & Theming Engine| C[Clustering Engine<br>Max 5 Domain Themes]
    C -->|Synthesis| D[Weekly Pulse Generator<br>Top 3 Themes | 3 Quotes | 3 Actions<br>≤250 Words]
    D -->|MCP Tool Call| E[Google Docs MCP<br>Publish / Update One-Page Note]
    D -->|MCP Tool Call| F[Gmail MCP<br>Create Draft Email with Note / Link]
```

### Stage 1: Ingestion & Preprocessing
- **Data Source**: Public review exports from Apple App Store and Google Play Store covering the last **8–12 weeks**.
- **Standardized Fields**: Star rating, review title, body text, and submission timestamp.
- **Sanitization**: Filter out spam, normalize text encoding, and strip incidental personal identifiers before downstream analysis.

### Stage 2: Clustering & Theming Engine
- **Theme Ceiling**: Group ingested reviews into a **maximum of 5 high-level product themes** tailored to Swiggy (e.g., *delivery speed & partner behavior, order accuracy & packaging, Instamart & grocery availability, pricing & Swiggy One coupons, app performance & GPS tracking*).
- **Distillation**: Evaluate cluster density and sentiment severity to isolate the **Top 3 most prominent themes** for the current reporting period.

### Stage 3: One-Page Weekly Pulse Generation
The engine synthesizes the top clusters into an executive-ready summary note that adheres to strict scannability requirements (**≤250 words total**). The note MUST contain exactly:
1. **Top 3 Themes**: A clear breakdown of what users are discussing most frequently.
2. **Real User Quotes**: Exactly **3 verbatim snippets** extracted directly from actual user reviews (zero synthetic or invented phrasing).
3. **Action Ideas**: Exactly **3 concrete next steps** or improvement recommendations directly grounded in the identified themes.

### Stage 4: Stakeholder Delivery via MCP
- **Google Docs**: Automatically create or update the weekly pulse document in Google Workspace for team review and inline commenting.
- **Gmail**: Automatically generate a draft email addressed to the creator (or a designated team alias) containing the summary or a direct link to the published Google Doc.

---

## 4. Technical Architecture: The MCP-First Principle

A foundational architectural requirement of Review Pulsator is the **MCP-First (Model Context Protocol)** integration pattern.

### Why MCP over Bespoke REST Wiring?
- **No OAuth Boilerplate**: The codebase must **NOT** implement standalone OAuth 2.0 client flows, token management, refresh loops, or custom HTTP REST client code for Google Workspace APIs.
- **Standardized Tool Calling**: All external mutations—specifically creating/updating Google Documents and creating Gmail drafts—must be executed by invoking standardized tools exposed by local or environment-provided **MCP servers**.
- **Separation of Concerns**: Decouples core analytical intelligence (review aggregation, NLP clustering, and LLM summarization) from external delivery mechanisms, ensuring high portability across AI agent runtimes and IDE environments.

---

## 5. Critical Guardrails & Constraints

Any feature development, prompt engineering, or pipeline modification must strictly enforce the following rules:

> [!IMPORTANT]
> **Strict Privacy & Zero PII**
> Absolutely NO Personally Identifiable Information (PII) may be included in any generated artifact. Usernames, email addresses, device IDs, IP addresses, and location data must be stripped. All verbatim user quotes must be fully anonymized prior to publication.

> [!WARNING]
> **Compliance & Public Data Only**
> Strictly utilize public review exports or official public store APIs. Automated web scraping behind store login walls or any data extraction method violating Apple App Store or Google Play Terms of Service (ToS) is explicitly prohibited.

> [!CAUTION]
> **Scannability & Presentation Scope**
> Never exceed the presentation limits: cluster into at most 5 themes, highlight exactly the Top 3 themes in the final note, and maintain an executive word count of **≤250 words** where applicable.

---

## 6. Definition of Done (DoD) Summary
A complete cycle of Review Pulsator is validated when:
1. `8–12 weeks` of mobile review data is ingested and sanitized.
2. Reviews are clustered into `≤5 themes`, with the `Top 3` extracted alongside `3 verbatim anonymous quotes` and `3 grounded action items`.
3. The summary is successfully written to a Google Doc via an **MCP tool call**.
4. A draft notification email is successfully created in Gmail via an **MCP tool call**.
5. The final output is verified for `≤250 words` and `100% PII exclusion`.

---

## 8. Production Deployment Topology

Review Pulsator is architected for zero-maintenance cloud production deployment:

* **Frontend Presentation Layer (`/dashboard`) → Vercel**:
  * Hosted as a responsive, reactive web application via **Vercel** (`https://review-pulsator.vercel.app`).
  * Configured via `vercel.json` with API proxy rewrite rules forwarding `/api/*` traffic cleanly to the backend microservice without CORS friction.
* **Backend AI Inference Engine (`Dockerfile` & `dashboard_server.py`) → Hugging Face Spaces**:
  * Hosted as a containerized Docker SDK Space on **Hugging Face Spaces** listening on port `7860`.
  * Executes the 4-stage pipeline, prompts Groq Llama 3.3 70B, and communicates with the remote Google Workspace MCP microservice via HTTP SSE.
